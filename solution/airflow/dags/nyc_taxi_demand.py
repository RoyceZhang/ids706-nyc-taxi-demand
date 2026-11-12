"""Scheduled taxi ETL; follows the instructor's TaskFlow / XCom-path pattern."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from airflow.decorators import dag, task
from taxi import etl

@dag(dag_id='nyc_taxi_demand', start_date=datetime(2025,2,1,tzinfo=timezone.utc),
     schedule='0 6 * * *', catchup=False, max_active_runs=1,
     max_active_tasks=4, default_args={'retries':2,'retry_delay':timedelta(seconds=15)},
     tags=['IDS706','taxi','regression'])
def nyc_taxi_demand():
    @task
    def ingest_trips():
        return etl.download('trips')
    @task
    def ingest_zones():
        return etl.download('zones')
    @task
    def clean_trips(path):
        out=etl.DATA/'clean_trips.parquet'; etl.clean_trips(path).to_parquet(out,index=False); return str(out)
    @task
    def clean_zones(path):
        out=etl.DATA/'clean_zones.parquet'; etl.clean_zones(path).to_parquet(out,index=False); return str(out)
    @task
    def merge_features(trips, zones):
        import pandas as pd
        frame=etl.aggregate(pd.read_parquet(trips),pd.read_parquet(zones))
        out=etl.DATA/'hourly.parquet'; frame.to_parquet(out,index=False); return str(out)
    @task
    def load_postgres(path):
        import pandas as pd
        return etl.load(pd.read_parquet(path))
    @task
    def analyze_postgres(_loaded):
        return etl.export_and_analyze()
    # Two independent branches run concurrently under the existing LocalExecutor.
    trips=clean_trips(ingest_trips())
    zones=clean_zones(ingest_zones())
    analyze_postgres(load_postgres(merge_features(trips,zones)))

nyc_taxi_demand()
