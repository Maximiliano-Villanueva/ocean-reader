# Docker Compose — edge gateway, DNS, and verification

## App URL (after `docker compose up`)

Open the UI at:

**`http://localhost:8080/`**

If you set **`GATEWAY_HTTP_PORT`** in `.env`, use that port instead of **8080**. OpenAPI: **`http://localhost:8080/docs`** (same host/port).

Postgres still stores historical rows from older features (e.g. legacy `documents` / `chunks`); **validation uploads are not persisted** as corpus rows.

## Mental model

- **Traefik** is the single **public-facing HTTP port** (default **8080→80** in the container). It routes **`/api/*`**, **`/docs`**, **`/openapi.json`**, and **`/redoc`** to **FastAPI**, and everything else to the **SPA** (nginx). This mirrors a typical cloud pattern: Ingress / Application Gateway → API + UI.
- **gateway-auth** is an optional **forwardAuth** companion: Traefik asks it whether the inbound request may continue. When **`EDGE_AUTH_ENABLED=true`**, callers must send **`Authorization: Bearer <EDGE_API_TOKEN>`** (or **`X-Api-Token`**) on **every** routed path (including `/docs`).
- **CoreDNS** runs **inside** the Compose network only for **service discovery emulation**: zone **`ocean-read.internal`** with **`gateway.ocean-read.internal`** → Traefik task IP (regenerated whenever the CoreDNS container starts). On the host, UDP **`127.0.0.1:${COREDNS_UDP_PORT:-55353}`** exposes the resolver so workloads on your laptop can **`dig`** the same names you might use behind a private hosted zone in AWS/GCP.

**Production / public URL:** add another Traefik dynamic file under `infra/traefik/dynamic/` (or generate it in CI) that repeats the same routers and middlewares with **`Host(\`customer.app.example\`)`**. Terminate TLS at your cloud load balancer or enable a cert resolver on Traefik; keep the path split identical so the UI keeps using same-origin **`/api`**.

## Services (`docker-compose.yml`)

| Service | Role |
|---------|------|
| **traefik** | API gateway: routing, optional forwardAuth, rate limit on `/api` (not on the dedicated SSE route), security headers |
| **gateway-auth** | forwardAuth handler (`/auth`); **204** when allowed |
| **coredns** | Internal DNS zone `ocean-read.internal` (see above) |
| **db** | Postgres + pgvector |
| **pgadmin** | pgAdmin 4 web UI for Postgres (**`127.0.0.1:${PGADMIN_PUBLISH:-5050}`**); register server host **`db`**, port **5432** |
| **backend** | FastAPI (not published on the host; only via Traefik) |
| **frontend** | nginx + static SPA (not published on the host; only via Traefik) |
| **schema-agent** | Conversational schema authoring (ADK → **Ollama** `gemma4:e4b` on the host) |

### Hostnames Traefik accepts (file `infra/traefik/dynamic/ocean.yml`)

`ocean-read.local`, `localhost`, `127.0.0.1`, `gateway.ocean-read.internal`, and the Docker hostname **`traefik`**. Add your real FQDN with an extra dynamic file as above; **do not** widen this list to `.*` in production without understanding the trade-off.

### Published ports (host)

| Port | Service |
|------|---------|
| **`GATEWAY_HTTP_PORT` (default 8080)** | Traefik **web** entrypoint |
| **`PGADMIN_PUBLISH` (default 5050)** | pgAdmin on **127.0.0.1** only |
| **`POSTGRES_PUBLISH` (default 15432)** | Postgres on the host (avoids clashing with a local **5432**; set **5432** if you want the usual port) |
| **`COREDNS_UDP_PORT` (default 55353)** | CoreDNS on **127.0.0.1** only |

## Host requirements

1. **Ollama** on the host at **`OLLAMA_BASE_URL`** (default **`http://host.docker.internal:11434`** from containers). Pull **`gemma4:e4b`** before using the schema assistant or LLM validation features:

```bash
ollama pull gemma4:e4b
```

Used when **`VALIDATION_LLM_FALLBACK_ENABLED`**, **`VALIDATION_OPEN_ENDED_ENABLED`**, **`VALIDATION_LLM_VISION_ENABLED`**, or the schema agent is active.

2. **schema-agent** starts with **`./start.sh`**. Optional check: `./scripts/verify_docker_llm.sh`. See [`SCHEMA_AGENT.md`](SCHEMA_AGENT.md).

Optional:

- **`EDGE_AUTH_ENABLED`** / **`EDGE_API_TOKEN`** — see **`.env.example`**. When auth is on, rebuild the **frontend** image so **`VITE_EDGE_API_TOKEN`** is baked in.

## Bring up

**One command** from repo root: **`./start.sh`** — rebuilds images, waits for **`/api/health`** and **`/api/projects`**, seeds **Default workspace** + **`wine_quality` @ `1.0`** (retries + verification; exits **1** if seeding fails). No separate seed step. With **`EDGE_AUTH_ENABLED=true`**, set **`EDGE_API_TOKEN`** in `.env` before **`./start.sh`** so health, seed, and the frontend build arg stay aligned.

```bash
./start.sh
```

Or invoke Compose directly (foreground):

```bash
docker compose up --build
```

Detached:

```bash
docker compose up --build -d
```

Stop the stack:

```bash
./stop.sh
```

If you need Postgres on host port **5432** (and nothing else is using it):

```bash
POSTGRES_PUBLISH=5432 docker compose up --build -d
```

**502 from Traefik** (`/api/*`) usually means the **backend was not accepting connections** yet (first boot runs `alembic` before `uvicorn`) or the backend container crashed. Compose now gates **Traefik** on the **backend** passing **`GET /api/health`** (see `backend` `healthcheck` in `docker-compose.yml`). If Traefik never becomes ready, check **`docker compose logs backend`** for migration or DB errors.

## Backend tests (pytest in Compose)

From the **repository root**, run the full **`backend/tests`** suite against the Compose **Postgres** (migrations applied, same **`DATABASE_URL`** as the **`backend`** service):

```bash
docker compose run --rm \
  -v "$(pwd)/backend/src:/app/src:ro" \
  -v "$(pwd)/backend/tests:/app/tests:ro" \
  backend sh -c "pip install -q pytest pytest-asyncio && alembic upgrade head && pytest tests/ -q"
```

Mount **`src`** so the container sees your working tree (the image alone may be stale). Do not use `pip install -e '.[dev]'` with a read-only **`src`** mount.

Details and layout: [TESTING.md](TESTING.md).

**Database URL in Compose:** the **`backend`** service sets **`DATABASE_URL`** to **`postgresql+asyncpg://…@db:5432/…`** using **`POSTGRES_*`** from `docker-compose.yml`. A host-only **`DATABASE_URL`** in `.env` (for example **`127.0.0.1:15432`**) is **not** passed into the container, so Alembic and the API always reach the Compose **`db`** service.

## Verification (after healthy)

**Validation + M2 audit (PDF hash, snapshot sub-resources, list filter):**

```bash
./scripts/verify_docker_validation_e2e.sh
```

Uses **`GATEWAY_HTTP_PORT`** (and edge auth headers when enabled). Requires **`backend/.venv`** with PyMuPDF to generate a tiny PDF on the host, or set **`OCEAN_VERIFY_PYTHON`** to a Python that has **`fitz`**.

**Edge (canonical):**

```bash
curl -sS http://127.0.0.1:8080/api/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
```

**Internal DNS from the host** (optional):

```bash
dig @127.0.0.1 -p "${COREDNS_UDP_PORT:-55353}" +short gateway.ocean-read.internal
```

**OpenAPI** (through the edge):

- http://127.0.0.1:8080/docs

**With edge auth enabled**, health checks need a bearer:

```bash
curl -sS -H "Authorization: Bearer $EDGE_API_TOKEN" http://127.0.0.1:8080/api/health
```

## Logs

The **Logs** link in the UI (`/logs`) calls **`GET /api/logs/containers`** and **`/api/logs/containers/{id}/tail`** on the backend. The backend mounts **`/var/run/docker.sock`** (read-only) and lists containers labeled with this Compose project (`COMPOSE_PROJECT_NAME`, default **`ocean-read`**). **Security:** the socket is powerful—keep **`LOG_VIEWER_ENABLED=false`** and remove the mount in any shared or production-like environment. When **`LOG_VIEWER_TOKEN`** is set, the browser must send **`X-Log-Viewer-Token`** (bake **`VITE_LOG_VIEWER_TOKEN`** into the frontend image).

**CLI** (host):

```bash
docker compose logs -f traefik
docker compose logs -f backend
docker compose logs -f coredns
```

## Tear down

```bash
docker compose down
```

Remove volumes (Postgres + uploads):

```bash
docker compose down -v
```

That deletes the **named volumes** (`ocean_pgdata`, `ocean_uploads`, `ocean_pgadmin`, and `airflow-db-data` when the Airflow profile created it). The next **`./start.sh`** starts with empty volumes until migrations repopulate the schema.

## Persistence, test cleanup, Airflow, and local files

### What survives `./start.sh` / `docker compose up`

- **`./start.sh`** only runs **`docker compose up --build -d`**. It does **not** use **`docker compose down -v`**, so **Postgres** and **upload** data stay on disk between sessions.
- **`./stop.sh`** runs **`docker compose down`** **without** **`-v`**, so **named volumes are retained**.

### Where data lives (not in the git tree)

| Storage | Compose volume | Mounted in |
|---------|----------------|------------|
| Postgres (schema; may include legacy tables from older migrations) | `ocean_pgdata` | `db` → `/var/lib/postgresql/data` |
| pgAdmin settings / saved servers | `ocean_pgadmin` | `pgadmin` → `/var/lib/pgadmin` |
| Reserved upload volume | `ocean_uploads` | `backend` → `/data/uploads` |
| Airflow metadata (optional **airflow** profile) | `airflow-db-data` | Airflow Postgres |

Deleting all **`projects`** via the SQL helpers **CASCADE**-removes linked rows that still have FKs from legacy schemas.

### Clean DB + upload files while testing (keep volumes)

From repo root (**`db`** must be running; **`backend`** is used if running, otherwise a one-off **`docker compose run`** clears uploads):

```bash
./scripts/empty_dev_testing.sh
```

- **`scripts/empty_dev_database.sh`** — only SQL: delete all **`projects`**, ensure default organization.
- **`scripts/empty_dev_testing.sh`** — runs the SQL script, then clears **`/data/uploads`** on volume **`ocean_uploads`**.

### Check Airflow (optional profile)

The repository **no longer ships an ingestion DAG**. Optional **`airflow`** profile is only for **custom** DAGs you mount under **`infra/airflow/dags/`** (see **`infra/airflow/README.md`**).

1. Start stack with Airflow: **`docker compose --profile airflow up -d`**.
2. Web UI: **`http://127.0.0.1:${AIRFLOW_UI_PORT:-8794}/`** — sign in (default `airflow` / `airflow`); DAG list is on **Home** (`/home`).
3. Example — list DAGs from the scheduler container:

```bash
docker compose exec airflow-scheduler airflow dags list
```

### Other local paths (outside Compose volumes)

- **`.env`** at repo root — not committed; set **`OLLAMA_BASE_URL`**, **`LLM_MODEL`**, tokens.
- **Host Ollama** weights — Ollama’s own data directory (e.g. **`~/.ollama/models`** on macOS).
- **Backend on host** (not Docker): default **`UPLOAD_ROOT`** is **`./uploads`** relative to cwd — separate from the **`ocean_uploads`** volume.

## Environment overrides

Compose reads **`.env`** when present — see **`.env.example`**. **`DATABASE_URL`** inside containers uses the hostname **`db`**, not **`127.0.0.1`**.
