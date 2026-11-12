"""Run the instructor's actual streamed graph and retain reproducible evidence."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.langgraph.graph import stream_solution_loop
from taxi.etl import ART
p=argparse.ArgumentParser(); p.add_argument('--dataset',default='datasets/taxi/taxi_hourly.csv'); a=p.parse_args()
ART.mkdir(parents=True,exist_ok=True)
started=time.perf_counter(); result=None
with (ART/'events.jsonl').open('w') as out:
    for event in stream_solution_loop(dataset_path=a.dataset,target_column='pickup_count',max_cycles=3,model='deterministic'):
        event['elapsed_seconds']=time.perf_counter()-started
        out.write(json.dumps(event,default=str)+'\n'); out.flush()
        if event['type']=='node_completed':print(event['node'],event.get('note'),flush=True)
        if event['type']=='error':raise RuntimeError(event['message'])
        if event['type']=='run_completed':result=event['result']
if not result:raise RuntimeError('No successful completion event')
result['runtime_seconds']=time.perf_counter()-started
result['input_origin']='file-only fallback; PostgreSQL unverified' if 'file_only' in a.dataset else 'PostgreSQL export (verify export_manifest.json)'
(ART/'evaluation.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps({k:result[k] for k in ['cycles','best_val_mae','best_spec','holdout_metrics','test_evaluations','runtime_seconds']},indent=2))
