"""Validation domain — schema lifecycle, mapping, resolution, rule engine, PDF layout.

Modules
-------
``pdf_blocks`` — TextBlock layout, ``parse_pdf_blocks``, ``infer_section_labels``.
``extractors_wine`` — regex + layout candidates (M1 wine).
``mapping`` — ``map_candidates_to_schema``, ``check_inconsistencies``.
``resolution`` — deterministic ``ExtractionCandidate`` selection.
``engine`` — ``validate_schema`` (PASS/FAIL); M3 ``cross_field_rules`` / ``groups``.
``expression_evaluator`` — sandboxed boolean/arithmetic DSL (no ``eval``).
``repeating_groups`` — section-scoped list/table row extraction + row rule checks.
``schema_dsl`` — ``collect_schema_dsl_errors`` for API validation of advanced bodies.
``outcomes`` — :class:`FieldValidationError`, :class:`FieldRuleOutcome`, :class:`ValidationReport`.
``pipeline_result`` — ``PipelineValidationResult`` (adds AMBIGUOUS).
``lifecycle`` — schema version state for the API.
"""
