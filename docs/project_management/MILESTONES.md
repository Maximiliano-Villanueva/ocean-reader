# Validation engine milestones

Canonical product vocabulary lives in [`docs/document_validation_docs/`](../document_validation_docs/). This file is the **rolling tracker** (manageable in one place).

| Milestone | Theme | Status | Acceptance (high level) |
|-----------|--------|--------|-------------------------|
| **M1** | Validation MVP — pipeline + evidence | **Done** (2026-05-02) | 8-stage PDF pipeline; `PASS`/`FAIL`/`AMBIGUOUS`; `schema.json` + `clean`/`noisy` corpus; TC-UNIT/INTG/API catalog in pytest; HTTP tests need Postgres in CI |
| **M2** | Auditability | **Done** (in progress on gateway UI) | Persist validation runs, snapshots, history, `pdf_hash`, candidates/blocks APIs |
| **M3** | Advanced rules | **Done** (backend) | Cross-field + repeating groups + DSL + tests; see [`M3_CHECKLIST.md`](M3_CHECKLIST.md) |
| **M4** | UX evidence | Partial | PDF bbox viewer shipped during M3 work; full inspection UX still open |
| **M5** | Platformization | Pending | Multi-tenant ops, authz, scale |
| **M6** | Intelligence (non-core) | Pending | Optional assist; **never** replace deterministic validation |

**Current focus:** Harden **M2** history/PDF UX and optional **M3.1** schema-editor wireframe. See [`M1_CHECKLIST.md`](M1_CHECKLIST.md), [`M3_CHECKLIST.md`](M3_CHECKLIST.md).
