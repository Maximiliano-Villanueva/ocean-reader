"""Validation domain — schema lifecycle, mapping, resolution, rule engine, PDF layout.

Modules
-------
``pdf_blocks`` — TextBlock layout, ``parse_pdf_blocks``, ``infer_section_labels``.
``extractors_wine`` — regex + layout candidates (M1 wine).
``mapping`` — ``map_candidates_to_schema``, ``check_inconsistencies``.
``resolution`` — deterministic ``ExtractionCandidate`` selection.
``engine`` — ``validate_schema`` (PASS/FAIL).
``pipeline_result`` — ``PipelineValidationResult`` (adds AMBIGUOUS).
``lifecycle`` — schema version state for the API.
"""
