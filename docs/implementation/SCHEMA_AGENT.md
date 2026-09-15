# Schema authoring agent (Ollama)

Conversational schema editor: chat left, live schema right. Immutable versions are still published through the existing validation-schema API.

## Services

| Service | Port | Role |
|---------|------|------|
| `schema-agent` | 8081 (internal) | Ollama chat + backend DSL validate |
| **Ollama (host)** | 11434 | **Gemma 4 E4B** — `gemma4:e4b` |
| `backend` | 8000 | Proxies `POST /api/projects/{id}/schema-agent/chat`, DSL validate internal route |

## Start (Mac / dev)

```bash
# On the host
ollama pull gemma4:e4b
ollama serve   # if not already running

cp .env.example .env
./start.sh
```

Containers reach Ollama via **`OLLAMA_BASE_URL=http://host.docker.internal:11434`** (see `docker-compose.yml`).

## API

**Frontend → backend**

`POST /api/projects/{project_id}/schema-agent/chat`

```json
{
  "messages": [{"role": "user", "content": "Add a field for invoice total"}],
  "schema_body": { "version": "3", "fields": {}, "rules": [] },
  "sample_pdf_note": "optional: user attached sample.pdf — …"
}
```

Response: `{ "reply": "…", "schema_body": { … } }`

**Agent → backend (internal)**

`POST /api/internal/validate-schema-body` — `{ "body": { … } }` → `{ "ok": true, "errors": [] }`

## Agent package

See [`schema_agent/AGENTS.md`](../../schema_agent/AGENTS.md).

## Open-ended runtime

Whenever a schema defines an ``open_ended`` block, validation **always** runs those fields through **Ollama** (no extra env flag required). Agent output is **normalized** (aliases, regex hints, open_ended placement) and **DSL-validated** with up to four repair turns before returning.

## Tests

- `tests/domain/validation/test_open_ended_*.py` — DSL + mocked Ollama
- `tests/api/test_internal_schema_validate.py` — internal validate route
- `tests/domain/validation/test_pipeline_wine_csv_fixtures.py` — rich PDF corpus, LLM off
- `@pytest.mark.llm` — live Ollama (excluded from default CI)
