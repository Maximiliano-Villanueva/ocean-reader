# Validation engine milestones

Canonical product vocabulary lives in [`docs/document_validation_docs/`](../document_validation_docs/). This file is the **rolling tracker** (manageable in one place).

| Milestone | Theme | Status | Acceptance (high level) |
|-----------|--------|--------|-------------------------|
| **M1** | Validation MVP — pipeline + evidence | **Done** (2026-05-02) | 8-stage PDF pipeline; `PASS`/`FAIL`/`AMBIGUOUS`; `schema.json` + `clean`/`noisy` corpus; TC-UNIT/INTG/API catalog in pytest; HTTP tests need Postgres in CI |
| **M2** | Auditability | Pending | Persist validation runs, immutable audit trail, export |
| **M3** | Advanced rules | Pending | Cross-field / conditional rules beyond range + presence |
| **M4** | UX evidence | Pending | Rich PDF highlight / inspection for each error |
| **M5** | Platformization | Pending | Multi-tenant ops, authz, scale |
| **M6** | Intelligence (non-core) | Pending | Optional assist; **never** replace deterministic validation |

**Current focus:** **M2** auditability (see [`M1_CHECKLIST.md`](M1_CHECKLIST.md) for M1 closure notes).
