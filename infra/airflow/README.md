# Optional Airflow profile

The **`airflow`** Compose profile starts Airflow’s scheduler + web UI for **custom orchestration**. It is **not** part of the Ocean Read validation pipeline (no bundled DAGs).

Mount your own DAGs under **`infra/airflow/dags/`** if you use this profile. The directory may be empty in a validation-only checkout.

See root **`docker-compose.yml`** (`--profile airflow`) and **`docs/DOCKER.md`**.
