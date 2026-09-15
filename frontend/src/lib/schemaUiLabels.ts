/**
 * Plain-language labels for checklist authoring (user-facing copy).
 */

export const SCHEMA_UI = {
  libraryTitle: "Checklists",
  libraryLead:
    "Define what to extract from your documents and how to validate it. Each published version is immutable.",
  newSchema: "New checklist",
  editSchema: "Edit checklist",
  publish: "Publish version",
  saveDraft: "Save draft",
  testPdf: "Test with sample PDF",
  assistantTitle: "Checklist assistant",
  assistantLead: "Ask questions, add fields, or fix validation errors in plain language.",

  wizardStep1: "Document type",
  wizardStep2: "Fields to extract",
  wizardStep3: "Rules & reading",
  wizardStep4: "Test & finish",

  sectionStrict: "Fields to extract",
  sectionStrictLead: "Values the pipeline must find and validate. Missing or invalid values fail the run.",
  sectionOpenEnded: "Extra insights (optional)",
  sectionOpenEndedLead: "AI-extracted text. Informative items never change PASS or FAIL.",
  sectionCross: "Rules between fields",
  sectionCrossLead: "Relationships across multiple extracted values (e.g. total must equal subtotal + tax).",
  sectionGroups: "Repeating sections",
  sectionGroupsLead: "Tables or lists of rows (test results, line items) with per-row checks.",
  sectionPdf: "How to read the PDF",
  sectionPdfLead: "Controls parsing and when the AI helps with layout or scanned images.",
  sectionGlobal: "Global checks",
} as const;

export type SchemaOutlineSelection =
  | { kind: "welcome" }
  | { kind: "strict"; field: string }
  | { kind: "open_ended"; field: string }
  | { kind: "cross"; index: number }
  | { kind: "group"; key: string }
  | { kind: "settings" };

export type SchemaEditorLayoutMode = "workspace" | "simple" | "json" | "wizard";
