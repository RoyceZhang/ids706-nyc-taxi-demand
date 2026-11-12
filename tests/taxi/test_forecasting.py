import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from taxi import etl
from loop_runtime import chronological_partitions
from solution.langgraph import taxi_regression as reg
from solution.langgraph.graph import stream_solution_loop, get_status

@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(etl,'ART',tmp_path/'artifacts')
    monkeypatch.setattr(reg,'ART',tmp_path/'artifacts')
    zones=pd.DataFrame({'LocationID':[1,2], 'Borough':['A','B'],'Zone':['a','b'],'service_zone':['yellow','yellow']})
    hours=pd.date_range('2025-01-01','2025-02-01',freq='h',inclusive='left')
    trips=pd.DataFrame({'tpep_pickup_datetime':np.repeat(hours,2),'PULocationID':1})
    frame=etl.aggregate(trips,zones)
    path=tmp_path/'data.csv';frame.to_csv(path,index=False)
    return path,frame,zones

def test_zero_grid_counts_and_lag_boundaries(sample):
    _,df,_=sample
    assert len(df)==2*31*24
    assert df[df.LocationID.eq(2)].pickup_count.eq(0).all()
    assert df.pickup_count.sum()==1488
    one=df[df.LocationID.eq(1)].reset_index(drop=True)
    assert one.loc[:167,'lag_168'].isna().all()
    assert one.loc[168,'lag_168']==2
    assert (df.forecast_origin == df.target_hour).all()

def test_future_pickups_do_not_change_past_features(sample):
    _,original,zones=sample
    hours=pd.date_range('2025-01-01','2025-02-01',freq='h',inclusive='left')
    trips=pd.DataFrame({'tpep_pickup_datetime':np.repeat(hours,2),'PULocationID':1})
    extra=pd.DataFrame({'tpep_pickup_datetime':[pd.Timestamp('2025-01-15 10:00')]*100,'PULocationID':1})
    changed=etl.aggregate(pd.concat([trips,extra]),zones)
    cutoff=pd.Timestamp('2025-01-15 10:00')
    pd.testing.assert_frame_equal(original.loc[original.target_hour.le(cutoff),etl.FEATURES],changed.loc[changed.target_hour.le(cutoff),etl.FEATURES])
    assert changed.loc[(changed.LocationID==1)&(changed.target_hour==cutoff+pd.Timedelta(hours=1)),'lag_1'].iloc[0]==102

def test_duplicate_lookup_fails_closed(tmp_path):
    path=tmp_path/'zones.csv'
    pd.DataFrame({'LocationID':[1,1],'Borough':['A','A'],'Zone':['a','a'],'service_zone':['y','y']}).to_csv(path,index=False)
    with pytest.raises(ValueError,match='Duplicate'):etl.clean_zones(path)

def test_chronological_global_cutoffs(sample):
    train,val,test=chronological_partitions(sample[0])
    assert train.target_hour.max()<val.target_hour.min()<test.target_hour.min()
    assert val.target_hour.max()<test.target_hour.min()
    assert set(train.LocationID)==set(val.LocationID)==set(test.LocationID)
    assert train.target_hour.min()==pd.Timestamp('2025-01-08')

def test_classroom_graph_stream_budget_memory_and_seal(sample):
    assert get_status()['ready']
    events=list(stream_solution_loop(dataset_path=str(sample[0]),target_column='pickup_count',max_cycles=99))
    # Browser JSON.parse must accept every event (no NaN / Infinity).
    for event in events:json.dumps(event,allow_nan=False)
    assert events[-1]['type']=='run_completed'
    final=events[-1]['result']
    assert final['cycles']==3 and final['test_evaluations']==1
    assert len(final['memory']['history'])==3
    assert final['best_val_mae']==min(h['validation_metrics']['mae'] for h in final['memory']['history'])
    assert sum(e.get('node')=='holdout_eval' and e['type']=='node_started' for e in events)==1
    assert sum(e.get('route')=='memory' for e in events)==2
    for node in ['data_scientist','hypothesis_generator','ml_engineer','judge','holdout_eval']:
        start=next(i for i,e in enumerate(events) if e['type']=='node_started' and e.get('node')==node)
        end=next(i for i,e in enumerate(events) if e['type']=='node_completed' and e.get('node')==node)
        assert start<end
    saved=json.loads((reg.ART/'memory.json').read_text())
    assert len(saved['history'])==3
    assert 'holdout' not in json.dumps(saved) and 'test_evaluations' not in saved
    with pytest.raises(RuntimeError,match='already evaluated'):reg.holdout({'test_evaluations':1})

def test_test_labels_do_not_affect_selection(sample):
    path,df,_=sample
    before=list(stream_solution_loop(dataset_path=str(path),target_column='pickup_count',max_cycles=2))[-1]['result']
    df.loc[df.target_hour.ge('2025-01-27'),'pickup_count']=9999
    df.to_csv(path,index=False)
    after=list(stream_solution_loop(dataset_path=str(path),target_column='pickup_count',max_cycles=2))[-1]['result']
    assert before['best_spec']==after['best_spec']
    assert before['best_val_mae']==after['best_val_mae']
    assert before['holdout_metrics']['mae']!=after['holdout_metrics']['mae']

def test_postgres_transaction_idempotency_when_available(sample):
    import os
    if os.getenv('TAXI_INTEGRATION')!='1':pytest.skip('Requires actual PostgreSQL; set TAXI_INTEGRATION=1')
    first=etl.load(sample[1]);second=etl.load(sample[1])
    assert first==second=={'rows':1488,'pickups':1488}


def test_dag_structure_and_schedule():
    import ast
    tree=ast.parse(Path('solution/airflow/dags/nyc_taxi_demand.py').read_text())
    dag=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='nyc_taxi_demand')
    decorator=dag.decorator_list[0]
    args={x.arg:ast.literal_eval(x.value) for x in decorator.keywords if x.arg in {'schedule','max_active_runs','max_active_tasks','catchup'}}
    assert args=={'schedule':'0 6 * * *','catchup':False,'max_active_runs':1,'max_active_tasks':4}
    calls={n.name:n for n in dag.body if isinstance(n,ast.FunctionDef)}
    assert set(calls)=={'ingest_trips','ingest_zones','clean_trips','clean_zones','merge_features','load_postgres','analyze_postgres'}
