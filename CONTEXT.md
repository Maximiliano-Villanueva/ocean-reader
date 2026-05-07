# Ocean Read — domain context

**New here?** Read [`docs/ONBOARDING.md`](docs/ONBOARDING.md), then continue below.

**Docker app URL:** **`http://localhost:8080/`** (`GATEWAY_HTTP_PORT`). See [`README.md`](README.md).

## Product

**Deterministic PDF validation**: PDF → extraction → resolution → schema rules → **PASS/FAIL** + **evidence** per field.

## Multitenancy

| Concept | Meaning |
|--------|--------|
| **Organization** | Every **project** has `organization_id` (default org in dev). |
| **Project** | Owns **versioned validation schemas**. |

## Hexagonal layering (DDD)

| Layer | Path | Rule |
|-------|------|------|
| **Domain** | `ocean_read/domain/validation/` | Pure logic, no I/O. |
| **Application** | `ocean_read/application/` | Ports + services. |
| **Infrastructure** | `ocean_read/infrastructure/persistence/` | SQLAlchemy. |
| **HTTP** | `ocean_read/api/` | Routers. |

## API tags

**System**, **Workspace** (projects), **Validation**, **Logs** (dev).

## TDD

**`pytest`** under **`backend/tests/`**.
