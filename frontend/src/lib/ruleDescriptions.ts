/**
 * Human-readable labels for validation rules and run outcomes.
 */

const RULE_LABELS: Record<string, string> = {
  required: "Value required",
  range_validation: "Must be within allowed range",
  type_check: "Must match expected type",
  cross_field: "Cross-field rule",
};

/** Plain-language description of a validation rule id. */
export function describeValidationRule(rule: string): string {
  return RULE_LABELS[rule] ?? rule.replace(/_/g, " ");
}

/** Short explanation shown under the outcome banner. */
export function outcomeSummary(status: string): string {
  switch (status) {
    case "PASS":
      return "All required fields were found and passed the rules in the schema.";
    case "FAIL":
      return "At least one field failed a rule or was missing.";
    case "AMBIGUOUS":
      return "Multiple conflicting readings were found for at least one field — review candidates on the PDF.";
    default:
      return "";
  }
}
