# Ocean Read — Backend

Python package **`ocean_read`** (install from this directory). Detailed module map is in **[`../docs/BACKEND.md`](../docs/BACKEND.md)**; onboarding in **[`../docs/ONBOARDING.md`](../docs/ONBOARDING.md)**.

## Quick commands

```bash
cd backend
pip install -e ".[dev]"
pytest -q
export DATABASE_URL=postgresql+asyncpg://ocean:ocean@127.0.0.1:5432/ocean_read   # adjust if needed
alembic upgrade head
uvicorn ocean_read.main:app --reload --host 0.0.0.0 --port 8000
```

Set `DATABASE_URL`, `OLLAMA_BASE_URL`, `LLM_MODEL`, and `VALIDATION_LLM_FALLBACK_ENABLED` via environment (see **`.env.example`** in repo root).
