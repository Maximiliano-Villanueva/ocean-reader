# Retired RAG stack

This document **historically** described hybrid retrieval (BM25 + pgvector + LangGraph). That codebase path **has been removed**: no corpus router, no ingestion service, no agent graph, no embedding client.

**Current product:** deterministic PDF validation — see [`VALIDATION_ENGINE.md`](VALIDATION_ENGINE.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

Postgres may still contain **`documents`**, **`chunks`**, and **`messages`** tables from older Alembic revisions until you run a dedicated cleanup migration.
