# Backend layout (`ocean_read/`)

## Routers (`api/routers/`)

| Module | Role |
|--------|------|
| `system.py` | `/api/health` |
| `workspace.py` | Projects CRUD |
| `validation.py` | `GET .../validation-schemas`, `POST /api/validate-document` |
| `logs.py` | Dev log viewer |

## Services (`services/`)

| Module | Role |
|--------|------|
| `validation_pipeline.py` | PDF → extract → resolve → validate |
| `validation_llm.py` | Optional Ollama JSON extraction |
| `docker_logs.py` | Compose container logs |

## Domain (`domain/validation/`)

PDF blocks, extractors, resolution priority (`regex` > `layout` > `llm`), schema validation.

## Persistence (`infrastructure/persistence/`)

`SqlAlchemyWorkspaceRepository`, `SqlAlchemyValidationSchemaRepository`.

## Providers (`providers/ollama.py`)

`OllamaLLMClient` for validation fallback.

## Database models (`db/models.py`)

Includes **legacy** tables from older features. **`user_preferences`** is dropped by migration **`007_drop_user_prefs`**.
