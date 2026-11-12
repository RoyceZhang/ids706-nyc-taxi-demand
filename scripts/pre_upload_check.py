"""Check prepared submission files and recorded evidence without Docker or ML dependencies."""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md', 'GITHUB_UPLOAD.md', 'requirements-taxi.txt',
    'infra/compose.taxi.yml', 'infra/Dockerfile.taxi', 'infra/Dockerfile.taxi-airflow',
    'infra/Dockerfile.frontend', 'solution/airflow/dags/nyc_taxi_demand.py',
    'solution/langgraph/graph.py', 'solution/langgraph/taxi_regression.py',
    'taxi/etl.py', 'frontend/src/pages/SolutionLoopPage.tsx',
    'frontend/src/components/LiveSimpleLoopGraph.tsx', 'tests/taxi/test_forecasting.py',
    'evidence/airflow_execution.json', 'evidence/eda_postgres.png',
    'evidence/evaluation.json', 'evidence/export_manifest.json', 'evidence/selection_lock.json',
    *['screenshots/'+name+'.png' for name in ['airflow_success','airflow_graph','agent_graph','evaluation_results']],
]
for name in REQUIRED:
    assert (ROOT/name).is_file(), f'Missing submission file: {name}'
for p in (ROOT/'screenshots').glob('*.png'):
    header=p.read_bytes()[:24]
    assert header[:8]==b'\x89PNG\r\n\x1a\n', f'Invalid PNG: {p.name}'
    width,height=struct.unpack('>II',header[16:24])
    assert width>=800 and height>=400, f'Image too small: {p.name}'
load=lambda name:json.loads((ROOT/'evidence'/name).read_text())
airflow=load('airflow_execution.json')
assert airflow['first']['dag_run']['state']==airflow['repeat']['dag_run']['state']=='success'
assert airflow['branch_overlaps'], 'No recorded parallel execution intervals'
assert airflow['db']=='197160|3475204|265'
assert load('export_manifest.json')['sha256']==load('selection_lock.json')['dataset_sha256']
evaluation=load('evaluation.json')
assert evaluation['cycles']==3 and evaluation['test_evaluations']==1
assert evaluation['best_spec']['experiment_id']=='exp-2'
assert set(evaluation['holdout_metrics'])=={'mae','rmse','r2'}
assert evaluation['input_origin'].startswith('PostgreSQL export')
for line in (ROOT/'evidence/events.jsonl').read_text().splitlines():
    json.dumps(json.loads(line),allow_nan=False)
for name in ['README.md','GITHUB_UPLOAD.md','evidence/README.md','screenshots/README.md']:
    for target in re.findall(r'\]\(([^)]+)\)',(ROOT/name).read_text()):
        if not re.match(r'https?://',target):
            assert (ROOT/name).parent.joinpath(target.split('#')[0]).exists(), f'Broken link in {name}: {target}'
for p in ROOT.rglob('*'):
    if '.git' in p.parts or not p.is_file(): continue
    assert p.stat().st_size < 50*1024*1024, f'Unexpected large upload: {p.relative_to(ROOT)}'
    assert p.name not in {'.env','.env.local'}, f'Local credentials included: {p}'
print('PASS: required source, four real screenshot files, evidence consistency, README links, and upload file sizes.')
print('Recorded Docker result: 11 tests passed (author-supplied successful local verification output).')
print('No GitHub publication has been performed.')
