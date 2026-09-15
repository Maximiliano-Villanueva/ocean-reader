/**
 * Starter schemas for the guided new-schema wizard.
 */

export type WizardDocType = "invoice" | "lab_report" | "custom";

export const WIZARD_DOC_TYPES: {
  id: WizardDocType;
  title: string;
  description: string;
  icon: string;
  suggestedKey: string;
}[] = [
  {
    id: "invoice",
    title: "Invoice",
    description: "Numbers, dates, totals, bill-to details",
    icon: "🧾",
    suggestedKey: "invoice",
  },
  {
    id: "lab_report",
    title: "Lab report",
    description: "Measured values with min/max ranges",
    icon: "🔬",
    suggestedKey: "lab_report",
  },
  {
    id: "custom",
    title: "Custom",
    description: "Start from an empty template",
    icon: "✨",
    suggestedKey: "my_schema",
  },
];

export function bodyForWizardDocType(docType: WizardDocType): Record<string, unknown> {
  if (docType === "invoice") {
    return {
      version: "3",
      fields: {
        invoice_number: {
          type: "string",
          required: true,
          aliases: ["Invoice number", "Número de factura"],
        },
        total_due: {
          type: "number",
          required: true,
          aliases: ["Total due", "Importe por pagar"],
          semantic_role: "document_total",
        },
        issue_date: {
          type: "date",
          required: false,
          aliases: ["Issue date", "Fecha de emisión"],
          llm_fallback: true,
        },
      },
      rules: ["required", "range_validation", "type_check"],
      extraction: { understand_document: true, context_pass: "when_needed" },
      open_ended: {
        recipient_name: {
          extract_prompt: "Extract the bill-to recipient name",
          informative_only: true,
        },
      },
    };
  }
  if (docType === "lab_report") {
    return {
      version: "3",
      fields: {
        ph: {
          type: "number",
          required: true,
          min: 2.5,
          max: 4.5,
          aliases: ["pH", "Measured pH"],
        },
        alcohol: {
          type: "number",
          required: true,
          min: 8,
          max: 15,
          aliases: ["Alcohol", "Alcohol %"],
        },
        quality: {
          type: "number",
          required: true,
          min: 0,
          max: 10,
          aliases: ["Quality", "Quality score"],
        },
      },
      rules: ["required", "range_validation", "type_check"],
      extraction: { understand_document: true, context_pass: "when_needed" },
    };
  }
  return {
    version: "3",
    fields: {},
    rules: ["required", "range_validation", "type_check"],
    extraction: { understand_document: true, context_pass: "when_needed" },
  };
}
