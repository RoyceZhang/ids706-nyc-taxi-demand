"""Acceptance checks against real Airflow/PostgreSQL, never simulated success.

Start Compose first. Uses the Airflow REST API to unpause, trigger twice, poll,
and record real task timings. Exits nonzero if any required runtime check fails.
"""
import base64
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/taxi';ART.mkdir(parents=True,exist_ok=True)
DAG='nyc_taxi_demand'
BASE='http://127.0.0.1:8088/api/v1'
USER=os.getenv('AIRFLOW_ADMIN_USER','admin');PASSWORD=os.getenv('AIRFLOW_ADMIN_PASSWORD','admin')

def request(path,method='GET',body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(BASE+path,data=data,method=method,headers={'Authorization':'Basic '+base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode(),'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

def compose(*args):
    return subprocess.check_output(['docker','compose','-f',str(ROOT/'infra/compose.taxi.yml'),*args],cwd=ROOT,text=True)

def trigger(suffix):
    run_id='assignment_'+str(int(time.time()))+'_'+suffix
    request(f'/dags/{DAG}/dagRuns','POST',{'dag_run_id':run_id,'conf':{}})
    for _ in range(240):
        status=request(f'/dags/{DAG}/dagRuns/{run_id}')
        if status['state']=='failed':raise RuntimeError('DAG failed: '+run_id)
        if status['state']=='success':
            tasks=request(f'/dags/{DAG}/dagRuns/{run_id}/taskInstances')['task_instances']
            return {'dag_run':status,'tasks':tasks}
        time.sleep(5)
    raise TimeoutError(run_id)

# Wait for fresh builds / migrations and for the scheduler to discover the DAG.
for attempt in range(120):
    try:
        details=request(f'/dags/{DAG}/details');break
    except Exception:
        if attempt==119:raise
        time.sleep(5)
request(f'/dags/{DAG}','PATCH',{'is_paused':False})
first=trigger('first')
query='SELECT COUNT(*) AS rows,SUM(pickup_count) AS pickups,COUNT(DISTINCT "LocationID") AS zones FROM taxi_hourly'
first_db=compose('exec','-T','taxi-db','psql','-U','taxi','-d','taxi','-Atc',query).strip()
first_hash=json.loads((ART/'export_manifest.json').read_text())['sha256']
second=trigger('repeat')
second_db=compose('exec','-T','taxi-db','psql','-U','taxi','-d','taxi','-Atc',query).strip()
assert first_db==second_db=='197160|3475204|265',(first_db,second_db)
# Exact content check: repeat ETL must reproduce the same sorted database export.
assert first_hash==json.loads((ART/'export_manifest.json').read_text())['sha256'],'Export changed on repeated load'
assert (ROOT/'artifacts/taxi/eda_postgres.png').is_file()
assert json.loads((ART/'export_manifest.json').read_text())['source']=='PostgreSQL taxi_hourly'
from datetime import datetime
parse=lambda t:datetime.fromisoformat(t.replace('Z','+00:00'))
a=[t for t in first['tasks'] if t['task_id'] in {'ingest_trips','clean_trips'}]
b=[t for t in first['tasks'] if t['task_id'] in {'ingest_zones','clean_zones'}]
overlaps=[(x['task_id'],y['task_id']) for x in a for y in b if max(parse(x['start_date']),parse(y['start_date']))<min(parse(x['end_date']),parse(y['end_date']))]
(ART/'airflow_execution.json').write_text(json.dumps({'first':first,'repeat':second,'db':second_db,'branch_overlaps':overlaps,'dag_details':details},indent=2))
assert overlaps,'No overlapping branch tasks observed; inspect saved execution timings and rerun.'
# Airflow itself provides the declared cron and next scheduled logical date.
info=request(f'/dags/{DAG}')
(ART/'schedule.json').write_text(json.dumps(info,indent=2))
assert '0 6 * * *' in json.dumps(info)
assert info.get('next_dagrun') is not None,'Scheduler has not populated next_dagrun yet'
# Exercise actual database integration, then restore full January ETL and model inputs.
print(compose('exec','-T','-e','TAXI_INTEGRATION=1','gateway','python','-m','pytest','tests/taxi','-q'))
trigger('restore_after_tests')
print(compose('exec','-T','gateway','python','scripts/run_taxi.py'))
print('Verified real DAG executions, parallel task intervals, schedule, idempotent DB totals, PostgreSQL EDA, tests, and agent loop.')
print('Now run screenshots/capture.mjs to capture actual UI evidence.')
