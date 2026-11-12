These tests validate the assignment additions. They do not assert that Docker or
Airflow has run. PostgreSQL integration is skipped unless TAXI_INTEGRATION=1.
Run integration only against the disposable Compose taxi database: the test
replaces January data. Run the full real-data DAG afterward to restore its data.
