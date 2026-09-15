"""Internal APIs for companion services (schema agent, ops)."""

from __future__ import annotations

from fastapi import APIRouter

from ocean_read.domain.validation.schema_dsl import collect_schema_dsl_errors
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body
from ocean_read.schemas import ValidateSchemaBodyIn, ValidateSchemaBodyOut

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/validate-schema-body", response_model=ValidateSchemaBodyOut)
async def validate_schema_body(payload: ValidateSchemaBodyIn) -> ValidateSchemaBodyOut:
    """DSL validation used by the schema authoring agent (no project scope)."""

    normalized = normalize_schema_body(payload.body)
    errs = collect_schema_dsl_errors(normalized)
    return ValidateSchemaBodyOut(ok=not errs, errors=errs, normalized_body=normalized)
