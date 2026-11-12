from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'datasets/taxi'
ART = ROOT / 'artifacts/taxi'
START, END = pd.Timestamp('2025-01-01'), pd.Timestamp('2025-02-01')
SOURCES = {
    'trips': ('https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet', 'yellow_tripdata_2025-01.parquet'),
    'zones': ('https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv', 'taxi_zone_lookup.csv'),
}
FEATURES = ['LocationID', 'hour', 'weekday', 'day', 'weekend', 'lag_1', 'lag_24', 'lag_168']

def download(kind: str) -> str:
    url, name = SOURCES[kind]
    path = DATA / 'raw' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temp = path.with_suffix('.download')
        with urlopen(url, timeout=120) as response, temp.open('wb') as out:
            import shutil
            shutil.copyfileobj(response, out)
        temp.replace(path)
    return str(path)

def clean_trips(path: str) -> pd.DataFrame:
    # Only pickup time and zone define demand; fare/distance filters would bias counts.
    df = pd.read_parquet(path, columns=['tpep_pickup_datetime', 'PULocationID'])
    df['tpep_pickup_datetime'] = pd.to_datetime(df.tpep_pickup_datetime, errors='coerce')
    df['PULocationID'] = pd.to_numeric(df.PULocationID, errors='coerce')
    return df.loc[df.tpep_pickup_datetime.ge(START) & df.tpep_pickup_datetime.lt(END)
                  & df.PULocationID.notna()].copy()

def clean_zones(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = ['LocationID', 'Borough', 'Zone', 'service_zone']
    if not set(needed).issubset(df):
        raise ValueError('Zone schema mismatch')
    df = df[needed].copy()
    df['LocationID'] = pd.to_numeric(df.LocationID, errors='raise').astype(int)
    if df.LocationID.duplicated().any():
        raise ValueError('Duplicate zone keys would inflate demand')
    df[['Borough', 'Zone', 'service_zone']] = df[['Borough', 'Zone', 'service_zone']].fillna('Unknown')
    return df

def aggregate(trips: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    joined = trips.merge(zones, left_on='PULocationID', right_on='LocationID', how='inner', validate='many_to_one')
    counts = joined.assign(target_hour=joined.tpep_pickup_datetime.dt.floor('h')).groupby(['LocationID', 'target_hour']).size()
    # All lookup zones, including zones with no trips, get the entire month grid.
    grid = pd.MultiIndex.from_product([sorted(zones.LocationID), pd.date_range(START, END, freq='h', inclusive='left')], names=['LocationID', 'target_hour'])
    df = counts.reindex(grid, fill_value=0).rename('pickup_count').reset_index()
    df = df.merge(zones, on='LocationID', validate='many_to_one')
    for lag in [1, 24, 168]:
        df[f'lag_{lag}'] = df.groupby('LocationID', sort=False).pickup_count.shift(lag)
    # At wall-clock t, hour [t-1,t) is complete; forecast covers [t,t+1).
    df['forecast_origin'] = df.target_hour
    df['hour'] = df.target_hour.dt.hour
    df['weekday'] = df.target_hour.dt.dayofweek
    df['day'] = df.target_hour.dt.day
    df['weekend'] = (df.weekday >= 5).astype(int)
    # Preserve unavailable lags as NULL; model rows begin Jan 8, no fabricated history.
    ART.mkdir(parents=True, exist_ok=True)
    (ART/'quality.json').write_text(json.dumps({'clean_trips': len(trips), 'joined_trips': len(joined), 'unmatched_trips': len(trips)-len(joined), 'zones':len(zones), 'rows':len(df), 'zero_hours': int(df.pickup_count.eq(0).sum()), 'total_pickups':int(df.pickup_count.sum())}, indent=2))
    return df

def database_url() -> str:
    return os.environ.get('TAXI_DATABASE_URL', 'postgresql://taxi:taxi@localhost:5433/taxi')

def load(df: pd.DataFrame) -> dict:
    import psycopg2
    from psycopg2.extras import execute_values
    cols = list(df.columns)
    values = [tuple(None if pd.isna(v) else v.to_pydatetime() if isinstance(v, pd.Timestamp) else v.item() if hasattr(v, 'item') else v for v in row) for row in df.itertuples(index=False, name=None)]
    with psycopg2.connect(database_url()) as conn, conn.cursor() as cur:
        # One transaction and lock prevent readers seeing a partial month or concurrent writes.
        cur.execute("SELECT pg_advisory_xact_lock(706202501)")
        cur.execute('''CREATE TABLE IF NOT EXISTS taxi_hourly (
          "LocationID" integer NOT NULL, target_hour timestamp NOT NULL,
          pickup_count integer NOT NULL CHECK(pickup_count>=0), "Borough" text,
          "Zone" text, service_zone text, lag_1 double precision, lag_24 double precision,
          lag_168 double precision, forecast_origin timestamp, hour integer, weekday integer,
          day integer, weekend integer, PRIMARY KEY("LocationID", target_hour))''')
        cur.execute('DELETE FROM taxi_hourly WHERE target_hour >= %s AND target_hour < %s', (START.to_pydatetime(), END.to_pydatetime()))
        quoted = ','.join('"'+c+'"' for c in cols)
        execute_values(cur, f'INSERT INTO taxi_hourly ({quoted}) VALUES %s', values, page_size=5000)
        cur.execute('SELECT COUNT(*), SUM(pickup_count) FROM taxi_hourly')
        rows, pickups = cur.fetchone()
    return {'rows': rows, 'pickups': int(pickups)}

def export_and_analyze() -> str:
    import psycopg2
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with psycopg2.connect(database_url()) as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM taxi_hourly ORDER BY target_hour, "LocationID"')
        df = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA/'taxi_hourly.csv'
    temp = dest.with_suffix('.tmp')
    df.to_csv(temp, index=False)
    temp.replace(dest)
    # This visualization exclusively uses PostgreSQL query results.
    ART.mkdir(parents=True, exist_ok=True)
    daily = df.groupby(pd.to_datetime(df.target_hour).dt.date).pickup_count.sum()
    fig, ax = plt.subplots(figsize=(10,4))
    daily.plot(ax=ax, title='January 2025 yellow taxi pickups — PostgreSQL query')
    ax.set_ylabel('Daily pickups'); ax.set_xlabel('Pickup date'); fig.tight_layout()
    fig.savefig(ART/'eda_postgres.png', dpi=150); plt.close(fig)
    (ART/'export_manifest.json').write_text(json.dumps({'source':'PostgreSQL taxi_hourly', 'rows':len(df), 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}, indent=2))
    return str(dest)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--file-only', action='store_true'); p.add_argument('--export-only', action='store_true'); a=p.parse_args()
    if a.export_only:
        print(export_and_analyze())
    else:
        frame = aggregate(clean_trips(download('trips')), clean_zones(download('zones')))
        if a.file_only:
            dest = DATA/'taxi_hourly_file_only.csv'; frame.to_csv(dest,index=False)
            print(f'FILE-ONLY FALLBACK (not PostgreSQL verified): {dest}, rows={len(frame)}')
        else:
            print(load(frame)); print(export_and_analyze())
