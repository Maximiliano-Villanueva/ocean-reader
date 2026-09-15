/**
 * Help copy for Schema Studio controls (deterministic vs open-ended).
 */

export const SCHEMA_HELP = {
  strictIntro:
    "These are values the pipeline must find on the PDF. Missing or invalid values fail the run.",
  fieldName: "Internal ID used in reports and rules (snake_case, e.g. invoice_number).",
  fieldType: "Text, number, or date — controls how values are parsed and validated.",
  required: "When checked, a missing value fails validation.",
  aliases:
    "Words or labels printed on the PDF near this value — one per line. Used to locate the value.",
  regexHint:
    "Optional pattern right after the label. Be specific (include part of the label) to avoid false matches.",
  minMax: "Inclusive minimum and maximum for numbers. Leave blank if not needed.",
  onAmbiguity:
    "What to do when the PDF contains more than one match for this field.",
  semanticRole:
    "Optional hint for layout-aware extraction (recipient, total, line item, etc.).",
  llmFallback: "For dates, allow AI parsing when regex does not match (e.g. Spanish month names).",
  extractionHint: "One sentence telling the AI what to look for and what to ignore.",
  openEndedIntro:
    "AI-extracted insights. Use “report only” when the value should never change PASS or FAIL.",
  extractPrompt: "Describe what to pull from the document (required).",
  evaluatePrompt: "When not report-only: how to decide pass, fail, or ambiguous from the extracted text.",
  informativeOnly: "Show on the report without affecting whether the run passes or fails.",
  linkEvidence: "Attach PDF highlights to the result.",
  dependsOn: "Other field IDs whose values are passed into the prompt (comma-separated).",
  documentUnderstanding:
    "Read document structure before extracting fields (recommended).",
  contextPass: "Run contextual AI only when regex/layout missed, or always.",
  globalRules: "Checks applied to every strict field after extraction.",
  samplePdf:
    "Upload a sample PDF and preview extraction. Results are not saved; they feed the assistant.",
  judgeNonRegex:
    "After extraction, AI reviews non-regex picks. Rejected values are dropped or marked ambiguous.",
  readImages:
    "Analyze embedded images with AI (slower). Off by default; enable for scanned charts or stamps.",
  crossFieldIntro:
    "Rules that relate multiple fields (e.g. total must equal line items sum). Failures block PASS.",
  crossFieldExpression: "Comparisons and AND/OR across field IDs (safe expression language).",
  crossFieldFields: "Strict field IDs referenced in the expression (comma-separated).",
  repeatingIntro:
    "Extract rows from a table, list, or section and validate each row.",
  repeatingSection: "Heading or label that identifies the section in the PDF.",
  repeatingStructure: "Row layout: table columns, one line per row, or paragraph blocks.",
} as const;

export const ON_AMBIGUITY_OPTIONS = [
  { value: "", label: "Default (best_match)" },
  { value: "best_match", label: "Best match" },
  { value: "first", label: "First on page" },
  { value: "last", label: "Last on page" },
  { value: "highest_confidence", label: "Highest confidence" },
  { value: "any", label: "Any (first resolved)" },
] as const;

export const SEMANTIC_ROLE_OPTIONS = [
  { value: "", label: "— None —" },
  { value: "recipient", label: "Recipient" },
  { value: "issuer", label: "Issuer" },
  { value: "document_total", label: "Document total" },
  { value: "line_item", label: "Line item" },
] as const;

export const FIELD_TYPE_OPTIONS = [
  { value: "string", label: "Text (string)" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
] as const;

export const GLOBAL_RULE_OPTIONS = [
  { key: "required", label: "Required fields present" },
  { key: "type_check", label: "Type check" },
  { key: "range_validation", label: "Range validation (min/max)" },
] as const;
