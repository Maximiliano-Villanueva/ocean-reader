/** Human-readable labels for validation rule codes returned by the API. */

export function describeValidationRule(rule: string): string {
  switch (rule) {
    case "required":
      return "Required field — the pipeline must resolve exactly one value for this field before rules apply.";
    case "range_validation":
      return "Allowed range — numeric values must lie within the inclusive minimum and maximum defined in the schema.";
    case "type_check":
      return "Type conformance — the resolved value must match the schema type (for example, numeric fields must parse as numbers).";
    default:
      return `Engine rule «${rule}» — see schema definition for details.`;
  }
}

export function outcomeSummary(status: "PASS" | "FAIL" | "AMBIGUOUS"): string {
  switch (status) {
    case "PASS":
      return "All applicable checks completed successfully; no blocking rule violations were recorded.";
    case "FAIL":
      return "One or more schema rules failed; review each item below for expected constraints and evidence pulled from the PDF.";
    case "AMBIGUOUS":
      return "The extractor produced multiple conflicting candidates for at least one field; resolve document ambiguity or tighten extraction.";
    default:
      return "";
  }
}
