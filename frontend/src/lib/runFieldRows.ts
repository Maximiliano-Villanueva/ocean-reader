/**
 * Build user-facing field rows for a validation run detail view (schema vs extraction vs PDF).
 */

import type { ValidateDocumentResponse, ValidationEvidenceOut } from "../api";
import type { PipelineCandidate, PdfHighlight } from "./evidenceHighlights";
import { summarizeSchemaBody, type SchemaFieldSummary } from "./schemaSummary";

export type FieldRowStatus = "resolved" | "ambiguous" | "missing" | "failed" | "not_evaluated";

export type FieldCandidateRow = {
  valueLabel: string;
  evidenceText?: string;
  highlightId: string | null;
};

export type RunFieldRow = {
  field: string;
  expectedSummary: string;
  status: FieldRowStatus;
  statusLabel: string;
  /** Primary display when a single value was resolved. */
  extractedSummary: string;
  candidates: FieldCandidateRow[];
  /** All highlight ids for this field (jump to first by default). */
  highlightIds: string[];
};

function formatExpected(spec: SchemaFieldSummary): string {
  const parts: string[] = [spec.type];
  if (spec.required) parts.push("required");
  else parts.push("optional");
  if (spec.min != null || spec.max != null) {
    parts.push(`${spec.min ?? "…"} – ${spec.max ?? "…"}`);
  }
  if (spec.aliasCount > 0) parts.push(`${spec.aliasCount} aliases`);
  return parts.join(" · ");
}

function dedupeCandidatesForDisplay(cands: PipelineCandidate[]): PipelineCandidate[] {
  const seen = new Set<string>();
  const out: PipelineCandidate[] = [];
  for (const c of cands) {
    const key = formatValue(c.value);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function highlightsForField(highlights: PdfHighlight[], field: string): PdfHighlight[] {
  return highlights.filter((h) => h.field === field);
}

function highlightIdForCandidate(
  highlights: PdfHighlight[],
  field: string,
  cand: PipelineCandidate,
  index: number,
): string | null {
  const fieldHighlights = highlightsForField(highlights, field);
  if (cand.block_id) {
    const byBlock = fieldHighlights.find((h) => h.id.includes(cand.block_id!));
    if (byBlock) return byBlock.id;
  }
  if (typeof cand.page === "number") {
    const onPage = fieldHighlights.filter((h) => h.page === cand.page);
    if (onPage[index]) return onPage[index]!.id;
  }
  return fieldHighlights[index]?.id ?? fieldHighlights[0]?.id ?? null;
}

/** Status label and row status from report + candidates. */
function resolveFieldStatus(
  field: string,
  report: ValidateDocumentResponse,
  candidatesForField: PipelineCandidate[],
): FieldRowStatus {
  const amb = new Set((report.ambiguous_fields ?? []).map((a) => a.field));
  if (amb.has(field)) return "ambiguous";
  const failed = (report.results ?? []).some((e) => e.field === field);
  const failedOutcome = (report.field_rule_outcomes ?? []).some((o) => o.field === field && !o.passed);
  if (failed || failedOutcome) return "failed";
  const resolved = report.resolved_values;
  if (resolved && field in resolved) return "resolved";
  if (candidatesForField.length > 0) return "resolved";
  return "missing";
}

function statusLabel(status: FieldRowStatus): string {
  switch (status) {
    case "resolved":
      return "Resolved";
    case "ambiguous":
      return "Ambiguous";
    case "missing":
      return "Not found";
    case "failed":
      return "Rule failed";
    case "not_evaluated":
      return "Not evaluated";
    default:
      return status;
  }
}

/**
 * One row per schema field with extraction outcome and PDF highlight links.
 */
export function buildRunFieldRows(
  schemaSnapshot: Record<string, unknown> | null | undefined,
  report: ValidateDocumentResponse,
  candidates: PipelineCandidate[],
  highlights: PdfHighlight[],
): RunFieldRow[] {
  const summary = summarizeSchemaBody(schemaSnapshot ?? undefined);
  const fields = summary.fields.length > 0 ? summary.fields : inferFieldsFromData(report, candidates);

  const byField = new Map<string, PipelineCandidate[]>();
  for (const c of candidates) {
    const list = byField.get(c.field) ?? [];
    list.push(c);
    byField.set(c.field, list);
  }

  return fields.map((spec) => {
    const field = spec.name;
    const cands = byField.get(field) ?? [];
    const status = resolveFieldStatus(field, report, cands);
    const fieldHighlights = highlightsForField(highlights, field);
    const highlightIds = fieldHighlights.map((h) => h.id);

    const resolvedVal = report.resolved_values?.[field];
    let extractedSummary = "—";
    const candidateRows: FieldCandidateRow[] = [];

    const distinctValues = [...new Set(cands.map((c) => formatValue(c.value)))];

    if (status === "ambiguous" && distinctValues.length > 1) {
      const shown = dedupeCandidatesForDisplay(cands);
      shown.forEach((c, i) => {
        candidateRows.push({
          valueLabel: formatValue(c.value),
          evidenceText: c.evidence_text?.trim() || undefined,
          highlightId: highlightIdForCandidate(highlights, field, c, i),
        });
      });
      extractedSummary = distinctValues.join(" · ");
    } else if (resolvedVal !== undefined && resolvedVal !== null) {
      extractedSummary = formatValue(resolvedVal);
      const match = cands.find((c) => formatValue(c.value) === formatValue(resolvedVal)) ?? cands[0];
      if (match) {
        candidateRows.push({
          valueLabel: extractedSummary,
          evidenceText: match.evidence_text?.trim() || undefined,
          highlightId: highlightIdForCandidate(highlights, field, match, 0),
        });
      }
    } else if (cands.length >= 1) {
      const best = cands[0]!;
      extractedSummary = formatValue(best.value);
      candidateRows.push({
        valueLabel: extractedSummary,
        evidenceText: best.evidence_text?.trim() || undefined,
        highlightId: highlightIdForCandidate(highlights, field, best, 0),
      });
    }

    return {
      field,
      expectedSummary: formatExpected(spec),
      status,
      statusLabel: statusLabel(status),
      extractedSummary,
      candidates: candidateRows,
      highlightIds,
    };
  });
}

function inferFieldsFromData(
  report: ValidateDocumentResponse,
  candidates: PipelineCandidate[],
): SchemaFieldSummary[] {
  const names = new Set<string>();
  for (const c of candidates) names.add(c.field);
  for (const a of report.ambiguous_fields ?? []) names.add(a.field);
  if (report.resolved_values) {
    for (const k of Object.keys(report.resolved_values)) names.add(k);
  }
  return [...names].sort().map((name) => ({
    name,
    type: "unknown",
    required: false,
    aliasCount: 0,
  }));
}

/** Map highlight id from evidence object when present in report outcomes. */
export function highlightIdFromEvidence(
  highlights: PdfHighlight[],
  field: string,
  ev: ValidationEvidenceOut | null | undefined,
): string | null {
  if (!ev?.bbox) return highlightsForField(highlights, field)[0]?.id ?? null;
  const page = ev.page ?? 1;
  const match = highlights.find(
    (h) =>
      h.field === field &&
      h.page === page &&
      h.bbox.every((n, i) => Math.abs(n - (ev.bbox![i] ?? 0)) < 0.5),
  );
  return match?.id ?? highlightsForField(highlights, field)[0]?.id ?? null;
}
