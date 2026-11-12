# Recorded local execution evidence

These snapshots were copied from the user's successful Docker run in
`/Users/zhangrongsheng/Downloads/IDS706_NYC_Taxi/artifacts/taxi` on November 12,
2026. They are preserved separately from runtime outputs so a fresh clone keeps
submission evidence while remaining reproducible.

- `airflow_execution.json`: two successful runs, actual task intervals, overlapping
  trip/zone branches, and PostgreSQL totals `197160|3475204|265`.
- `schedule.json`: active DAG, cron `0 6 * * *`, scheduler metadata.
- `quality.json`: joined counts, zero-demand hours, rows and zone totals.
- `source_manifest.json`: official input schema, raw row count, sizes and hashes.
- `export_manifest.json`: PostgreSQL export row count and SHA-256.
- `selection_lock.json`: configuration locked before test scoring. Its dataset
  hash matches the PostgreSQL export hash.
- `evaluation.json`: all three validation experiments, selected model, final test
  metrics, once-per-run test counter and measured runtime.
- `events.jsonl`: actual CLI LangGraph event stream from the local run.
- `memory.json`: validation-only experiment memory.
- `eda_postgres.png`: visualization generated from a PostgreSQL query.
- `pre_upload_tests.txt`: fresh packaging checks: 22 passed, 1 PostgreSQL integration
  test skipped; the packaging process has no database access.
- `frontend_build.txt`: fresh successful TypeScript/Vite production build.

The successful full container test result was **11 passed, 3 warnings in 1.31s**,
as supplied in the user's terminal output from `python3 scripts/verify_local.py`.
This is distinct from the separate packaging-environment test result.

Transient Airflow `file_token` values are omitted from JSON snapshots. Other
recorded evidence values are preserved. No metrics or screenshots are simulated.
User-provided screenshots are stored in `../screenshots/`.
