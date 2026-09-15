/**
 * Client-side export helpers for validation runs and extracted field datasets.
 */

import type { ValidationRunDetailOut, ValidationRunSummary } from "../api";
import type { RunFieldRow } from "./runFieldRows";

/** Trigger a file download in the browser. */
export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function csvEscape(value: string): string {
  const v = value ?? "";
  if (/[",\n\r]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
}

function csvRow(cells: string[]): string {
  return cells.map((c) => csvEscape(String(c))).join(",");
}

/** Tabular export of validation history (one row per document). */
export function validationRunsToCsv(runs: ValidationRunSummary[]): string {
  const header = csvRow([
    "document_filename",
    "schema_key",
    "version_label",
    "outcome",
    "created_at",
    "run_id",
  ]);
  const rows = runs.map((r) =>
    csvRow([
      r.document_filename,
      r.schema_key,
      r.version_label,
      r.outcome,
      r.created_at ?? "",
      r.id,
    ]),
  );
  return [header, ...rows].join("\n");
}

/** JSON dataset of validation history summaries. */
export function validationRunsToJson(
  runs: ValidationRunSummary[],
  meta?: { projectName?: string; projectId?: string },
): string {
  return JSON.stringify(
    {
      exported_at: new Date().toISOString(),
      workspace: meta?.projectName ?? meta?.projectId ?? null,
      count: runs.length,
      runs,
    },
    null,
    2,
  );
}

/** Per-field extraction CSV for a single run (audit / AP / QC handoff). */
export function runExtractionToCsv(run: ValidationRunDetailOut, fieldRows: RunFieldRow[]): string {
  const meta = [
    `# Ocean Read — field extraction export`,
    `# document: ${run.document_filename}`,
    `# checklist: ${run.schema_key} v${run.version_label}`,
    `# outcome: ${run.outcome}`,
    `# run_id: ${run.id}`,
    `# exported: ${new Date().toISOString()}`,
    "",
  ];
  const header = csvRow(["field", "expected", "extracted", "status"]);
  const rows = fieldRows.map((r) => {
    const extracted =
      r.status === "ambiguous"
        ? r.candidates.map((c) => c.valueLabel).join(" | ")
        : r.extractedSummary;
    return csvRow([r.field, r.expectedSummary, extracted, r.statusLabel]);
  });
  return [...meta, header, ...rows].join("\n");
}

/** Full structured JSON for a single run (fields + validation report). */
export function runDetailToJson(run: ValidationRunDetailOut, fieldRows: RunFieldRow[]): string {
  return JSON.stringify(
    {
      exported_at: new Date().toISOString(),
      run_id: run.id,
      document_filename: run.document_filename,
      schema_key: run.schema_key,
      version_label: run.version_label,
      outcome: run.outcome,
      created_at: run.created_at,
      pdf_hash: run.pdf_hash ?? null,
      fields: fieldRows.map((r) => ({
        field: r.field,
        expected: r.expectedSummary,
        status: r.status,
        extracted:
          r.status === "ambiguous"
            ? r.candidates.map((c) => ({
                value: c.valueLabel,
                evidence: c.evidenceText ?? null,
              }))
            : r.extractedSummary,
      })),
      resolved_values: run.report.resolved_values ?? {},
      ambiguous_fields: run.report.ambiguous_fields ?? [],
      validation_results: run.report.results ?? [],
      field_rule_outcomes: run.report.field_rule_outcomes ?? [],
      open_ended_results: run.report.open_ended_results ?? [],
    },
    null,
    2,
  );
}
