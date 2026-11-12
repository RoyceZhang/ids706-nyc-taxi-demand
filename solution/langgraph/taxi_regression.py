"""Regression node bodies plugged into the instructor's unchanged classroom topology.

Rule-based agents are explicit, reproducible fallbacks; no LLM calls are claimed.
The Judge alone selects by validation MAE. Test outcomes never enter memory.
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
import pandas as pd
from taxi.etl import FEATURES, ART
from loop_runtime import regression_metrics, chronological_partitions


def step(node, note, **extra):
    return [{'node':node, 'note':note, 'used_llm':False, **extra}]


def data_scientist(state):
    train, val, _ = chronological_partitions(state['dataset_path'])
    profile = {'task':'one-hour-ahead regression', 'features':FEATURES,
               'n_train':len(train), 'n_validation':len(val),
               'train_start':str(train.target_hour.min()), 'train_end':str(train.target_hour.max()),
               'validation_start':str(val.target_hour.min()), 'validation_end':str(val.target_hour.max()),
               'notes':['Test labels excluded from profiling and selection.',
                        'Rolling one-hour forecasts; prior actual demand becomes available each hour.',
                        'Only shifted demand and known calendar features are allowed.'],
               'recommended_drops':['pickup_count','target_hour','forecast_origin','Borough','Zone','service_zone']}
    return {'profile':profile, 'steps':step('data_scientist','Chronological audit; holdout sealed',output=profile)}


def hypothesis(state):
    cycle = state.get('cycle',0)
    history = state.get('brief',{}).get('history',[])
    if cycle == 0:
        direction = 'Establish same-hour last-week seasonal naive demand.'
    elif cycle == 1:
        direction = 'Use boosted trees to combine recent demand with weekly seasonality and calendar effects.'
    else:
        prior = history[-1]['validation_metrics']['mae']
        baseline = history[0]['validation_metrics']['mae']
        direction = ('Increase tree capacity to capture zone interactions.' if prior < baseline else
                     'Reduce depth and learning rate to regularize a model that did not beat seasonality.')
    plan = {'direction':direction, 'evidence':history[-1] if history else None, 'focus':'validation MAE only'}
    return {'hypothesis':plan,'steps':step('hypothesis_generator',direction,output=plan)}


def model_for(spec):
    from xgboost import XGBRegressor
    return XGBRegressor(objective='reg:squarederror', tree_method='hist', n_jobs=2,
                        random_state=42, **spec['hyperparameters'])


def predict(spec, train, evaluation):
    if spec['model_family']=='seasonal_naive':
        return evaluation.lag_168.to_numpy(), None
    model = model_for(spec)
    model.fit(train[FEATURES], train.pickup_count)
    return model.predict(evaluation[FEATURES]).clip(0), model


def engineer(state):
    started=time.perf_counter()
    cycle=state.get('cycle',0)+1
    if cycle==1:
        spec={'experiment_id':'exp-1','model_family':'seasonal_naive','hyperparameters':{}}
    elif cycle==2:
        spec={'experiment_id':'exp-2','model_family':'xgboost_regressor',
              'hyperparameters':{'n_estimators':180,'max_depth':5,'learning_rate':0.08,'min_child_weight':10}}
    else:
        hist=state['memory']['history']
        improved=hist[-1]['validation_metrics']['mae'] < hist[0]['validation_metrics']['mae']
        spec={'experiment_id':'exp-3','model_family':'xgboost_regressor',
              'hyperparameters':{'n_estimators':260,'max_depth':7 if improved else 3,
                                 'learning_rate':0.05,'min_child_weight':15}}
    train,val,_=chronological_partitions(state['dataset_path'])
    pred,_model=predict(spec,train,val)
    metrics=regression_metrics(val.pickup_count,pred)
    duration=time.perf_counter()-started
    result={'status':'succeeded','validation_metrics':metrics,'duration_seconds':duration}
    return {'cycle':cycle,'experiment_spec':spec,'execution_result':result,
            'steps':step('ml_engineer',f"{spec['model_family']} · validation MAE={metrics['mae']:.4f}",
                         status='succeeded',experiment_id=spec['experiment_id'],model_family=spec['model_family'],
                         validation_metrics=metrics,duration_seconds=duration,spec=spec,output=result)}


def judge(state):
    score=state['execution_result']['validation_metrics']['mae']
    improved=score < state.get('best_val_mae',float('inf'))
    selected=state['experiment_spec'] if improved else state['best_spec']
    best=score if improved else state['best_val_mae']
    final=state['cycle']>=state['max_cycles']
    verdict={'action':'accept' if final else 'revise',
             'observation':f'Validation MAE {score:.4f}; best {best:.4f}. Lower is better.',
             'next_action':'Lock selected model and evaluate test once.' if final else 'Use the next bounded experiment.'}
    mem=dict(state.get('memory') or {'history':[],'lessons':[]})
    mem['history']=[*mem.get('history',[]),{'cycle':state['cycle'],'spec':state['experiment_spec'],
                     'validation_metrics':state['execution_result']['validation_metrics'],'verdict':verdict}]
    mem['lessons']=[*mem.get('lessons',[]),verdict['observation']]
    return {'verdict':verdict,'best_spec':selected,'best_val_mae':best,'memory':mem,
            'steps':step('judge',verdict['observation'],verdict=verdict)}


def memory(state):
    ART.mkdir(parents=True,exist_ok=True)
    path=ART/'memory.json'; temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(state['memory'],indent=2)); temp.replace(path)
    return {'steps':step('memory_writer','Persisted validation experiments and lessons')}


def context(state):
    return {'brief':state['memory'],'steps':step('context_builder','History and judge evidence → next hypothesis')}


def holdout(state):
    if state.get('test_evaluations',0):
        raise RuntimeError('Holdout already evaluated')
    train,val,test=chronological_partitions(state['dataset_path'])
    # Lock configuration before touching labels; refit selected model on train+validation.
    spec=state['best_spec']
    ART.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(Path(state['dataset_path']).read_bytes()).hexdigest()
    lock={'best_spec':spec,'best_val_mae':state['best_val_mae'],'dataset_sha256':digest,
          'test_start':'2025-01-27','protocol':'rolling one-hour forecast; refit train+validation'}
    (ART/'selection_lock.json').write_text(json.dumps(lock,indent=2))
    pred,model=predict(spec,pd.concat([train,val]),test)
    metrics=regression_metrics(test.pickup_count,pred)
    if model is not None:
        model.save_model(ART/'selected_model.json')
    pd.DataFrame({'target_hour':test.target_hour,'LocationID':test.LocationID,'actual':test.pickup_count,'prediction':pred}).to_csv(ART/'test_predictions.csv',index=False)
    memory(state)  # Persist the last cycle as well, without test results.
    return {'holdout_metrics':metrics,'test_evaluations':1,'stop_reason':'maximum_cycles_model_selected',
            'steps':step('holdout_eval','Selected model only; sealed test evaluated once',metrics=metrics)}

NODES={'data_scientist':data_scientist,'hypothesis_generator':hypothesis,'ml_engineer':engineer,
       'judge':judge,'memory_writer':memory,'context_builder':context,'holdout_eval':holdout}
