# Architecture

## Runtime diagram (logical)

```text
Browser (React)
    │  same-origin /api
    ▼
Traefik (gateway, optional edge auth)
    ▼
FastAPI (`ocean_read.main`)
    ├── Workspace (projects)
    ├── Validation (schemas + PDF POST)
    └── Logs (dev Docker tail)
    ▼
PostgreSQL (projects, validation_schemas; legacy tables may remain)
    │
Host Ollama ← optional LLM text completion for validation extraction fallback
```

## Domain-driven layout

See **[`CONTEXT.md`](../CONTEXT.md)** — domain logic stays free of FastAPI/SQLAlchemy; routers delegate to services and repositories.

## Retired components

Chat, corpus ingestion, hybrid retrieval, preference snippets, and internal job endpoints have been **removed from source**.
