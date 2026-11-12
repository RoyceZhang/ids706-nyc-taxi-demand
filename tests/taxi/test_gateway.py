import json
import os
from pathlib import Path
import pytest

@pytest.fixture
def gateway(tmp_path,monkeypatch):
    monkeypatch.setenv('PROJECT_DATA_DIR',str(tmp_path/'projects'))
    monkeypatch.setenv('LOOP_RUNS_PATH',str(tmp_path/'history.json'))
    monkeypatch.setenv('DATASETS_DIR',str(tmp_path))
    # Import existing instructor API without starting a TCP server.
    import sys
    sys.path.insert(0,str(Path('advanced').resolve()))
    from services.gateway.app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)

def test_catalog_and_deterministic_policy(gateway):
    response=gateway.get('/solution-loop/models')
    assert response.status_code==200
    assert response.json()['default']=='deterministic'
    assert gateway.get('/solution-loop/datasets').status_code==200

def test_missing_dataset_rejected(gateway):
    response=gateway.get('/solution-loop/stream',params={'dataset_path':'missing.csv','target_column':'pickup_count'})
    assert response.status_code==400

def test_actual_sse_contract_without_tcp_server(gateway,tmp_path,monkeypatch):
    import pandas as pd
    from taxi import etl
    from solution.langgraph import taxi_regression as reg
    monkeypatch.setattr(etl,'ART',tmp_path/'artifacts')
    monkeypatch.setattr(reg,'ART',tmp_path/'artifacts')
    hours=pd.date_range('2025-01-01','2025-02-01',freq='h',inclusive='left')
    zones=pd.DataFrame({'LocationID':[1],'Borough':['A'],'Zone':['a'],'service_zone':['yellow']})
    trips=pd.DataFrame({'tpep_pickup_datetime':hours,'PULocationID':1})
    path=tmp_path/'taxi.csv'; etl.aggregate(trips,zones).to_csv(path,index=False)
    response=gateway.get('/solution-loop/stream',params={'dataset_path':str(path),'target_column':'pickup_count','max_cycles':3,'model':'deterministic'})
    assert response.status_code==200
    assert response.headers['content-type'].startswith('text/event-stream')
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert not any(e['type']=='error' for e in events)
    assert events[-1]['type']=='run_completed'
    assert events[-1]['result']['test_evaluations']==1
    assert 'mae' in events[-1]['result']['holdout_metrics']
