# Guidance for AI coding agents (Cursor, etc.)

Human and AI contributors should start with **[`docs/ONBOARDING.md`](docs/ONBOARDING.md)**. It links every other doc (`ARCHITECTURE`, `BACKEND`, `FRONTEND`, `TESTING`, `DOCKER`) and the canonical domain sheet [`CONTEXT.md`](CONTEXT.md).

**Docker default app URL:** **`http://localhost:8080/`** (override with **`GATEWAY_HTTP_PORT`** in `.env`).

When changing behavior: run **`pytest`** in `backend/` (see [`docs/TESTING.md`](docs/TESTING.md)) when Python changes; keep routers thin and push rules into **`ocean_read/domain/`** or application services.
