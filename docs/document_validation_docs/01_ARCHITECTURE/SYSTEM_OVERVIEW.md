# System Overview — Ocean Read Document Validation Engine

## 1. What This System Is

Ocean Read is a **deterministic, evidence-first document validation engine**.

Given a PDF document and a versioned validation schema, it produces a structured verdict:

- `PASS` — the document satisfies every declared rule
- `FAIL` — one or more rules were violated; every failure is explained with evidence
- `AMBIGUOUS` — one or more fields had conflicting values that could not be resolved deterministically; human review is required

**This system is not an AI assistant.** There is no chat, no RAG, no probabilistic inference. LLMs are used in two controlled, deterministic roles only: (1) fallback extraction when regex and layout heuristics fail, and (2) schema authoring assistance. In both cases LLM output is constrained, temperature-zero, and subject to deterministic post-processing.

---

## 2. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Determinism** | Identical input always produces identical output. No randomness in the validation path. |
| **Evidence-first** | Every decision — extracted value, resolution choice, validation result — is traceable to a specific location in the source document (page, block, bounding box). |
| **Auditability** | Every validation run is stored as an immutable snapshot: PDF hash, all intermediate states, final result. Runs can be reproduced and compared. |
| **Schema-driven** | What to validate is declared in a versioned schema. The engine is generic; document-type knowledge lives in schemas, not code. |
| **Human-in-the-loop for ambiguity** | The system never silently picks one of several conflicting values. Ambiguity is surfaced explicitly. |
| **Defense-in-depth extraction** | Discovery pass first, gap-fill second, LLM last. Higher-confidence sources always win. |

---

## 3. High-Level Pipeline

```
PDF bytes
    │
    ▼
┌─────────────────────────────┐
│  1. BLOCK EXTRACTION        │  PyMuPDF, section-aware layout parse
│     TextBlock[]             │  text + page + bbox + section_label
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  2. DISCOVERY PASS          │  Extract all entities in every section
│     ExtractionCandidate[]   │  value + type + source + confidence + evidence
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  3. SCHEMA MAPPING          │  Match candidates → schema fields
│     FieldCandidateMap       │  per field: [] | [one] | [many]
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  4. GAP-FILL PASS           │  Targeted re-scan for unmatched fields
│     ExtractionCandidate[]   │  LLM / focused regex / layout re-pass
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  5. INCONSISTENCY CHECK     │  Fields with 2+ conflicting values
│     InconsistencyReport     │  → marks field AMBIGUOUS; all candidates exposed
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  6. RESOLUTION              │  Pick one value per field (deterministically)
│     ResolvedDocument        │  regex > layout > llm; tie → highest confidence
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  7. VALIDATION ENGINE       │  Apply schema rules to resolved values
│     ValidationError[]       │  required, range, type, cross-field, repeating groups
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  8. RESULT + EVIDENCE       │  PASS | FAIL | AMBIGUOUS
│     ValidationReport        │  per-field: value, rule, evidence, all candidates
└─────────────────────────────┘
               │
               ▼
        (Persisted as ValidationRun snapshot)
```

---

## 4. Multi-Tenancy Model

```
Organization  (one per paying customer)
    └── Project  (one per document type, team, or supplier)
            └── ValidationSchema  (versioned, one active at a time)
                    └── ValidationRun  (immutable run snapshot)
```

- **Organization**: top-level tenant boundary. All data is isolated per organization.
- **Project**: scoping unit. A project owns its schemas. One project = one domain of documents.
- **ValidationSchema**: the rules definition. Versioned immutably — editing creates a new version; prior versions are archived, never deleted.
- **ValidationRun**: a persisted record of a single validation execution. Immutable once created.

---

## 5. Hexagonal (Ports & Adapters) Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        HTTP Layer                             │
│  FastAPI routers — thin, no business logic                    │
│  ocean_read/api/routers/                                      │
└──────────────────────────┬────────────────────────────────────┘
                           │ calls
┌──────────────────────────▼────────────────────────────────────┐
│                     Application Layer                         │
│  Orchestration services, port interfaces                      │
│  ocean_read/application/                                      │
└──────────────────────────┬────────────────────────────────────┘
                           │ calls
┌──────────────────────────▼────────────────────────────────────┐
│                       Domain Layer                            │
│  Pure logic — no I/O, no framework dependencies               │
│  ocean_read/domain/validation/                                │
└──────────────────────────┬────────────────────────────────────┘
                           │ implemented by
┌──────────────────────────▼────────────────────────────────────┐
│                  Infrastructure Layer                         │
│  SQLAlchemy persistence, Ollama client, file I/O              │
│  ocean_read/infrastructure/                                   │
└───────────────────────────────────────────────────────────────┘
```

The domain layer has zero knowledge of FastAPI, SQLAlchemy, or any LLM provider. All I/O crosses through ports (abstract interfaces) defined in the application layer and implemented in infrastructure.

---

## 6. Key Constraints

- **No PDF storage**: PDFs are processed in memory and never persisted. Only a content hash is stored with each run.
- **No randomness in validation path**: LLM calls use `temperature=0`. Resolution is deterministic given a fixed candidate list.
- **Schema immutability**: A schema version is never mutated after creation. New edits produce new versions.
- **Evidence is mandatory**: Every validation decision must cite a source location in the document. There is no synthetic evidence.
- **AMBIGUOUS blocks validation**: A document with unresolved field ambiguity cannot receive a clean PASS. It receives AMBIGUOUS, surfacing all candidate values and their document locations for human review.

---

## 7. Technology Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| PDF parsing | PyMuPDF (fitz) | Fast, accurate block-level layout extraction with bounding boxes |
| API framework | FastAPI (async) | Async I/O, type-safe, OpenAPI auto-generation |
| Persistence | PostgreSQL + SQLAlchemy (async) | JSONB for schema bodies, relational for tenancy |
| LLM provider | Ollama (local) | Controlled, self-hosted, deterministic with temperature=0 |
| Frontend | React + TypeScript | Component-driven, typed |
| Testing | pytest + dataset-driven fixtures | Deterministic regression via synthetic PDF corpus |

---

## 8. Document Types Supported

The engine is document-type agnostic. Document-type knowledge is encoded in schemas. The initial test corpus uses wine lab reports as synthetic documents. Production targets include:

- Laboratory analysis reports / Certificates of Analysis (COA)
- QA inspection documents and checklists
- Regulatory compliance certificates

Any structured or semi-structured PDF can be validated if a schema is defined for it.

---

## 9. Cross-References

| Topic | Document |
|-------|----------|
| Detailed pipeline stage spec | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| Bounded contexts | `01_ARCHITECTURE/DDD_CONTEXT_MAP.md` |
| Data shapes per stage | `01_ARCHITECTURE/DATA_FLOW.md` |
| Domain entities and aggregates | `03_DOMAIN/DOMAIN_MODEL.md` |
| Extraction and discovery model | `03_DOMAIN/EXTRACTION_MODEL.md` |
| Resolution strategy | `03_DOMAIN/RESOLUTION_MODEL.md` |
| Rule engine and DSL | `03_DOMAIN/RULE_ENGINE.md` |
| Schema definition language | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Backend module map | `05_IMPLEMENTATION/BACKEND_OVERVIEW.md` |
| API contracts | `05_IMPLEMENTATION/API_SPEC.md` |
