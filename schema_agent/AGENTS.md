# Schema agent package

Conversational schema agent for Ocean Read. Calls **Ollama** (`gemma4:e4b`) via native ``/api/chat`` (no ADK tool roles).

## Layout

| Path | Role |
|------|------|
| `src/schema_agent/main.py` | FastAPI `/chat`, `/health` |
| `src/schema_agent/agent_runner.py` | Ollama chat, schema fence parsing, DSL repair turn |
| `src/schema_agent/ollama_client.py` | ``/api/chat`` HTTP client |
| `src/schema_agent/tools.py` | `validate_schema_body`, `apply_schema_patch`, capabilities |
| `src/schema_agent/ollama_probe.py` | Health check against host Ollama |

## Env (Compose / local)

| Variable | Default |
|----------|---------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` |
| `LLM_MODEL` | `gemma4:e4b` |
| `OCEAN_BACKEND_URL` | `http://backend:8000` |

## Run locally

```bash
ollama pull gemma4:e4b
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OCEAN_BACKEND_URL=http://127.0.0.1:8080  # via gateway or backend port
uvicorn schema_agent.main:app --host 0.0.0.0 --port 8081
```

## Docker

Built as service `schema-agent` from repo root `schema_agent/Dockerfile`.
