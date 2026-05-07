# Backend Overview — Module Map and Layer Responsibilities

## Technology

- **Language**: Python 3.13
- **Framework**: FastAPI (async)
- **ORM**: SQLAlchemy 2.x (async sessions)
- **Database**: PostgreSQL (JSONB for schema bodies and run snapshots)
- **Package manager**: uv
- **Source root**: `backend/src/ocean_read/`

---

## Hexagonal Layer Map

```
backend/src/ocean_read/
├── api/                        HTTP Layer
│   ├── routers/
│   │   ├── system.py           Health checks
│   │   ├── workspace.py        Project/org CRUD
│   │   ├── validation.py       Document validation + schema management
│   │   └── logs.py             Dev-only structured log access
│   ├── deps.py                 FastAPI dependencies (DB session, project guard)
│   └── routes.py               Router registration
│
├── application/                Application Layer
│   ├── ports/
│   │   ├── validation_schema_repository.py   Abstract port (interface)
│   │   └── validation_run_repository.py      Abstract port (M2)
│   ├── workspace/
│   │   └── workspace_service.py              Project/org application service
│   └── staging_import/                       (future: bulk import)
│
├── domain/                     Domain Layer — pure logic, no I/O
│   ├── validation/
│   │   ├── pdf_blocks.py       TextBlock, parse_pdf_blocks()
│   │   ├── extractors.py       SchemaAwareExtractor (generic, schema-driven)
│   │   ├── extractors_wine.py  Wine-specific extractors (Milestone 1, deprecated post-refactor)
│   │   ├── resolution.py       ExtractionCandidate, resolve_document_with_evidence()
│   │   ├── engine.py           validate_schema(), ValidationReport
│   │   ├── lifecycle.py        SchemaLifecycleStatus, can_use_for_validation()
│   │   ├── mapping.py          FieldCandidateMap, schema_mapping(), inconsistency_check()
│   │   └── exceptions.py       Domain exceptions
│   ├── policy/
│   │   ├── upload_path.py      File upload path policy
│   │   └── file_integrity.py   File hash computation
│   ├── tenancy/
│   │   └── organization.py     Organization domain rules
│   └── knowledge/              (future: reference datasets)
│
├── infrastructure/             Infrastructure Layer
│   └── persistence/
│       ├── validation_schema_sqlalchemy.py   SqlAlchemyValidationSchemaRepository
│       ├── validation_run_sqlalchemy.py      SqlAlchemyValidationRunRepository (M2)
│       └── workspace_sqlalchemy.py           SqlAlchemyWorkspaceRepository
│
├── providers/                  External service adapters
│   └── ollama.py               OllamaLLMClient (async, temperature=0)
│
├── services/                   Application orchestration services
│   ├── validation_pipeline.py  ValidationPipelineService — wires all pipeline stages
│   ├── validation_llm.py       LLM fallback extraction service
│   └── docker_logs.py          Dev-only log streaming
│
├── db/
│   ├── base.py                 SQLAlchemy base, mixins (UUID PK, timestamps)
│   ├── models.py               ORM models: Organization, Project, ValidationSchema, ValidationRun
│   └── session.py              Async session factory
│
├── schemas/                    Pydantic request/response models (HTTP layer only)
│   └── __init__.py             ValidateDocumentResponse, ValidationFieldErrorOut, etc.
│
├── config.py                   Settings (Pydantic BaseSettings, env-driven)
└── main.py                     FastAPI app factory
```

---

## Layer Responsibilities

### HTTP Layer (`api/`)

- **Owns**: Request validation, response serialization, HTTP error mapping.
- **Must not**: Contain business logic, query the database directly, or call domain functions.
- **Rule**: Routers call application services or repositories only through the application layer. They translate HTTP concepts (form fields, status codes) into domain concepts.

### Application Layer (`application/`)

- **Owns**: Orchestration of domain logic, port definitions, transaction boundaries.
- **Must not**: Contain business rules (those live in domain). Must not contain SQL.
- **Ports**: Abstract interfaces that infrastructure implements. Example: `ValidationSchemaRepository` is defined as an abstract class here; `SqlAlchemyValidationSchemaRepository` implements it in infrastructure.

### Domain Layer (`domain/`)

- **Owns**: All business rules, validation logic, extraction algorithms, resolution strategy.
- **Must not**: Import FastAPI, SQLAlchemy, `httpx`, or any I/O library.
- **Testing**: All domain functions must be unit-testable with no fixtures or mocks. They take plain Python objects and return plain Python objects.

### Infrastructure Layer (`infrastructure/`)

- **Owns**: Persistence implementations (SQLAlchemy repositories), async query logic.
- **Must not**: Contain business rules. Must not be called directly from the HTTP layer.
- **Repository pattern**: Each repository class receives an `AsyncSession` in its constructor and is constructed per-request by the dependency injection system.

### Services Layer (`services/`)

- **Owns**: Pipeline orchestration (wires domain stages together), LLM integration.
- **Note**: This is technically part of the application layer but is separated for clarity.
- **`validation_pipeline.py`**: The one place where all pipeline stages are wired together. This is the single function that the HTTP router calls for document validation.

### Providers Layer (`providers/`)

- **Owns**: Low-level clients for external services (Ollama, future: cloud LLMs, object storage).
- **Must not**: Contain business logic. Providers are pure I/O adapters.

---

## Key Files Reference

### `domain/validation/pdf_blocks.py`

- `TextBlock` (frozen dataclass — includes optional `section_label`, `font_size_max`)
- `infer_section_labels(blocks) -> list[TextBlock]`
- `parse_pdf_blocks(data: bytes) -> list[TextBlock]` (runs inference before return)

### `domain/validation/lifecycle.py`

- `SchemaLifecycleStatus` (Enum)
- `can_use_for_validation(status) -> bool`

### `domain/validation/mapping.py`

- `FieldEntry` — per-schema-field status: `found` | `missing` | `ambiguous`
- `map_candidates_to_schema(candidates, schema_fields) -> dict[str, FieldEntry]`
- `check_inconsistencies(field_map) -> InconsistencyReport`
- `unmatched_schema_candidates(...)` — candidates not mapping to any schema key

### `domain/validation/pipeline_result.py`

- `PipelineValidationResult` — end-to-end status including **AMBIGUOUS**

### `domain/validation/resolution.py`

- `ExtractionCandidate` (frozen dataclass)
- `SOURCE_PRIORITY: dict[str, int]`
- `resolve_field_candidate(field, candidates) -> ExtractionCandidate`
- `resolve_document_with_evidence(candidates) -> tuple[ResolvedDocument, EvidenceMap]`
- `resolve_from_field_map(field_map) -> tuple[ResolvedDocument, EvidenceMap]` (only `found` entries)

### `domain/validation/engine.py`

- `FieldValidationError` (frozen dataclass)
- `ValidationReport` (frozen dataclass; PASS/FAIL from rule engine only)
- `validate_schema(resolved, schema_body, ...) -> ValidationReport` (alias `validate_wine_style_schema`)

### `services/validation_pipeline.py`

- `run_wine_pdf_validation(...) -> PipelineValidationResult` (`PASS` | `FAIL` | `AMBIGUOUS`)

### `infrastructure/persistence/validation_schema_sqlalchemy.py`

- `SqlAlchemyValidationSchemaRepository`
  - `create_version(...)`, `get_active(...)`, `get_by_version(...)`, `list_versions(...)`, `list_grouped_by_project(...)`, `archive(...)`, `soft_delete(...)`

---

## Database Schema

### `organizations`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `name` | varchar(255) | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `projects`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `organization_id` | UUID | FK → organizations |
| `name` | varchar(255) | |
| `settings` | jsonb | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `validation_schemas`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `project_id` | UUID | FK → projects |
| `schema_key` | varchar(128) | Logical schema name |
| `version_label` | varchar(64) | Human-readable version |
| `status` | varchar(32) | `active \| archived \| deleted` |
| `body` | jsonb | The schema DSL as JSON |
| `archived_at` | timestamptz? | Set when archived |
| `deleted_at` | timestamptz? | Soft delete timestamp |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique constraint**: `(project_id, schema_key, version_label)`.
**Partial unique index**: `(project_id, schema_key)` WHERE `status = 'active'` — enforces one active version at a time.

### `validation_runs` (Milestone 2)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `project_id` | UUID | FK → projects |
| `schema_key` | varchar(128) | |
| `schema_version` | varchar(64) | |
| `pdf_hash` | varchar(71) | `"sha256:" + hex` |
| `status` | varchar(32) | `PASS \| FAIL \| AMBIGUOUS` |
| `snapshots` | jsonb | Full intermediate state |
| `created_at` | timestamptz | |

---

## Settings (`config.py`)

All settings are loaded from environment variables via Pydantic `BaseSettings`.

| Setting | Env var | Default | Description |
|---------|---------|---------|-------------|
| `database_url` | `DATABASE_URL` | required | PostgreSQL async URL |
| `validation_llm_fallback_enabled` | `VALIDATION_LLM_FALLBACK_ENABLED` | `false` | Enable LLM fallback in extraction |
| `ollama_base_url` | `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `ollama_model` | `OLLAMA_MODEL` | `"llama3"` | Model to use for extraction fallback |
| `max_validate_bytes` | `MAX_VALIDATE_BYTES` | `31457280` (30MB) | Max PDF upload size |

---

## Running the Backend

```bash
cd backend

# Install dependencies
uv sync

# Run tests
pytest tests/

# Start dev server
uvicorn ocean_read.main:app --reload --port 8000

# Or via Docker Compose (full stack)
docker compose up
```

---

## Cross-References

| Topic | Document |
|-------|----------|
| API endpoint contracts | `05_IMPLEMENTATION/API_SPEC.md` |
| Pipeline stage implementation | `05_IMPLEMENTATION/PIPELINE_IMPLEMENTATION.md` |
| Domain model | `03_DOMAIN/DOMAIN_MODEL.md` |
| DDD context map | `01_ARCHITECTURE/DDD_CONTEXT_MAP.md` |
