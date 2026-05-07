# Ocean Read — Document Validation Engine Documentation

This is the complete source of truth for the Document Validation Engine. Start here if you are new. Every decision, design, and implementation detail is documented in one of the sections below.

**New to the project?** Read in this order:
1. [`01_ARCHITECTURE/SYSTEM_OVERVIEW.md`](01_ARCHITECTURE/SYSTEM_OVERVIEW.md) — what it is and how it works
2. [`01_ARCHITECTURE/PIPELINE_DESIGN.md`](01_ARCHITECTURE/PIPELINE_DESIGN.md) — the 8-stage pipeline in detail
3. [`03_DOMAIN/DOMAIN_MODEL.md`](03_DOMAIN/DOMAIN_MODEL.md) — entities, aggregates, value objects
4. [`05_IMPLEMENTATION/BACKEND_OVERVIEW.md`](05_IMPLEMENTATION/BACKEND_OVERVIEW.md) — code structure

---

## Folder Index

### `00_PRODUCT/` — Product definition
| File | Contents |
|------|----------|
| `USER_PERSONAS.md` | Who uses this system |
| `USE_CASES.md` | What they do with it |

### `01_ARCHITECTURE/` — System design
| File | Contents |
|------|----------|
| `SYSTEM_OVERVIEW.md` | Big picture, principles, tech stack |
| `PIPELINE_DESIGN.md` | All 8 pipeline stages, inputs/outputs, algorithms |
| `DDD_CONTEXT_MAP.md` | Bounded contexts and their relationships |
| `DATA_FLOW.md` | Exact data shapes at every stage boundary |

### `02_MILESTONES/` — Delivery plan
| File | Contents |
|------|----------|
| `MILESTONE_1_VALIDATION_MVP.md` | ✅ MVP: end-to-end deterministic validation |
| `MILESTONE_2_AUDITABILITY.md` | Run history, full snapshots, reproducibility |
| `MILESTONE_3_ADVANCED_RULES.md` | Cross-field rules, repeating groups |

### `03_DOMAIN/` — Domain model
| File | Contents |
|------|----------|
| `DOMAIN_MODEL.md` | All aggregates, entities, and value objects |
| `EXTRACTION_MODEL.md` | Discovery pass, candidates, inconsistency |
| `RESOLUTION_MODEL.md` | Deterministic resolution algorithm |
| `RULE_ENGINE.md` | Rule types, extensibility, DSL |
| `VALIDATION_SCHEMA.md` | Full schema DSL specification |

### `04_TESTING/` — Testing strategy
| File | Contents |
|------|----------|
| `TEST_STRATEGY.md` | Principles, layers, success criteria |
| `DATASET_STRATEGY.md` | Wine dataset, fixture corpus, ground truth |
| `TEST_GENERATOR_SPEC.md` | How to generate HTML/PDF fixtures |
| `WINE_DATASET_PIPELINE.md` | End-to-end wine corpus test flow |
| `TEST_CASES.md` | Complete test case catalog |

### `05_IMPLEMENTATION/` — Code specs
| File | Contents |
|------|----------|
| `BACKEND_OVERVIEW.md` | Module map, layers, database schema |
| `API_SPEC.md` | All HTTP endpoints and contracts |
| `PIPELINE_IMPLEMENTATION.md` | Code design per stage, refactor guide |
| `FRONTEND_SPEC.md` | Views, UX flows, component architecture |

### `06_DECISIONS/` — Architecture Decision Records
| File | Contents |
|------|----------|
| `ADR_001.md` | Why RAG was removed from the architecture |
| `ADR_002.md` | PyMuPDF vs Docling decision |
| `ADR_003.md` | LLM usage rules (controlled, deterministic, last-resort) |

### `07_OPERATIONS/` — Operational guidance
| File | Contents |
|------|----------|
| `LOGGING_STRATEGY.md` | Structured log events, format, log levels |

---

## Key Concepts (Quick Reference)

| Concept | Definition |
|---------|-----------|
| **PASS** | Document satisfies all schema rules |
| **FAIL** | One or more rules violated; each failure has evidence |
| **AMBIGUOUS** | One or more fields have conflicting values; human review needed |
| **Schema** | JSON definition of what a valid document looks like (fields + rules) |
| **ExtractionCandidate** | One extractor's hypothesis about a field value, with evidence |
| **Discovery pass** | Exhaustive first extraction sweep — schema-agnostic |
| **Gap-fill pass** | Targeted second sweep for fields not found in discovery |
| **Resolution** | Deterministic selection of one value per field (regex > layout > llm) |
| **Evidence** | Block ID + page + bbox pointing to exact location in the PDF |
| **Run snapshot** | Immutable persisted record of every pipeline stage for one validation run |
