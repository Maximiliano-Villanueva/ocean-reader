/**
 * Build PDF overlay highlights from validation evidence, errors, and pipeline snapshots.
 * Bboxes use PyMuPDF layout coordinates: ``[x0, y0, x1, y1]`` in PDF points, origin top-left.
 */

import type { OpenEndedFieldResultOut, ValidationEvidenceOut, ValidateDocumentResponse } from "../api";

export type HighlightKind = "field" | "error" | "ambiguous" | "candidate" | "block";

export type PdfHighlight = {
  id: string;
  page: number;
  bbox: [number, number, number, number];
  label: string;
  kind: HighlightKind;
  /** Optional link to ledger / error row */
  field?: string;
  rule?: string;
};

export type PipelineBlock = {
  id: string;
  page: number;
  bbox?: number[] | null;
  text?: string;
};

export type PipelineCandidate = {
  field: string;
  value?: unknown;
  source?: string;
  confidence?: number;
  block_id?: string;
  page?: number;
  bbox?: number[] | null;
  evidence_text?: string;
};

function isValidBbox(b: unknown): b is [number, number, number, number] {
  if (!Array.isArray(b) || b.length < 4) return false;
  const [x0, y0, x1, y1] = b;
  return (
    typeof x0 === "number" &&
    typeof y0 === "number" &&
    typeof x1 === "number" &&
    typeof y1 === "number" &&
    x1 > x0 &&
    y1 > y0
  );
}

function evidenceToHighlight(
  ev: ValidationEvidenceOut,
  opts: { id: string; label: string; kind: HighlightKind; field?: string; rule?: string },
): PdfHighlight | null {
  if (!isValidBbox(ev.bbox)) return null;
  const page = typeof ev.page === "number" && ev.page > 0 ? ev.page : 1;
  return {
    id: opts.id,
    page,
    bbox: ev.bbox,
    label: opts.label,
    kind: opts.kind,
    field: opts.field,
    rule: opts.rule,
  };
}

/** Cross-field rules may attach ``by_field`` maps instead of a single block bbox. */
function highlightsFromEvidenceValue(
  ev: ValidationEvidenceOut | Record<string, unknown> | null | undefined,
  opts: { idPrefix: string; label: string; kind: HighlightKind; field?: string; rule?: string },
): PdfHighlight[] {
  if (!ev || typeof ev !== "object") return [];
  const raw = ev as Record<string, unknown>;
  const byField = raw.by_field;
  if (byField && typeof byField === "object") {
    const out: PdfHighlight[] = [];
    let i = 0;
    for (const [fname, sub] of Object.entries(byField as Record<string, ValidationEvidenceOut>)) {
      if (!sub || typeof sub !== "object") continue;
      const h = evidenceToHighlight(sub, {
        id: `${opts.idPrefix}-${fname}-${i++}`,
        label: `${opts.label} · ${fname}`,
        kind: opts.kind,
        field: fname,
        rule: opts.rule,
      });
      if (h) out.push(h);
    }
    return out;
  }
  const single = evidenceToHighlight(ev as ValidationEvidenceOut, {
    id: opts.idPrefix,
    label: opts.label,
    kind: opts.kind,
    field: opts.field,
    rule: opts.rule,
  });
  return single ? [single] : [];
}

/** Highlights from API validation report (errors + rule ledger evidence). */
export function highlightsFromReport(report: ValidateDocumentResponse): PdfHighlight[] {
  const out: PdfHighlight[] = [];
  let n = 0;

  for (const r of report.results ?? []) {
    if (!r.evidence) continue;
    out.push(
      ...highlightsFromEvidenceValue(r.evidence, {
        idPrefix: `err-${r.field}-${r.rule}-${n++}`,
        label: `${r.field} (${r.rule})`,
        kind: "error",
        field: r.field,
        rule: r.rule,
      }),
    );
  }

  for (const o of report.field_rule_outcomes ?? []) {
    if (!o.evidence) continue;
    const kind: HighlightKind = o.passed ? "field" : "error";
    out.push(
      ...highlightsFromEvidenceValue(o.evidence, {
        idPrefix: `out-${o.field}-${o.rule}-${n++}`,
        label: `${o.field} · ${o.rule}`,
        kind,
        field: o.field,
        rule: o.rule,
      }),
    );
  }

  return dedupeHighlights(out);
}

/** Highlights from open-ended LLM fields when ``link_evidence`` is true. */
export function highlightsFromOpenEnded(results: OpenEndedFieldResultOut[] | undefined): PdfHighlight[] {
  const out: PdfHighlight[] = [];
  let n = 0;
  for (const r of results ?? []) {
    for (const ev of r.evidence ?? []) {
      if (!isValidBbox(ev.bbox)) continue;
      const page = ev.page > 0 ? ev.page : 1;
      const evalLabel = r.informative_only
        ? "info"
        : r.evaluation
          ? r.evaluation
          : "open";
      out.push({
        id: `oe-${r.field}-${ev.block_id || n}-${n++}`,
        page,
        bbox: ev.bbox,
        label: `${r.field} (${evalLabel})`,
        kind: r.evaluation === "ambiguous" ? "candidate" : r.informative_only ? "field" : "field",
        field: r.field,
      });
    }
  }
  return dedupeHighlights(out);
}

export type HighlightsFromCandidatesOptions = {
  /**
   * Schema fields with conflicting extractions (``report.ambiguous_fields``).
   * Only these use the dashed candidate style; other fields use resolved ``field`` (green).
   */
  ambiguousFields?: Iterable<string>;
};

/** All extraction candidates from a persisted run snapshot. */
export function highlightsFromCandidates(
  candidates: PipelineCandidate[],
  opts?: HighlightsFromCandidatesOptions,
): PdfHighlight[] {
  const ambiguous = new Set(opts?.ambiguousFields ?? []);
  const out: PdfHighlight[] = [];
  let n = 0;
  for (const c of candidates) {
    if (!isValidBbox(c.bbox)) continue;
    const page = typeof c.page === "number" && c.page > 0 ? c.page : 1;
    const src = c.source ? ` · ${c.source}` : "";
    const field = c.field;
    const kind: HighlightKind =
      ambiguous.size > 0 && field && ambiguous.has(field) ? "candidate" : "field";
    out.push({
      id: `cand-${field}-${c.block_id ?? n}-${n++}`,
      page,
      bbox: c.bbox,
      label: `${field}${src}`,
      kind,
      field,
    });
  }
  return dedupeHighlights(out);
}

function findBlockForNeedle(blocks: PipelineBlock[], needle: string): PipelineBlock | null {
  const n = needle.trim().toLowerCase().replace(/\s+/g, " ");
  if (n.length < 3) return null;
  let best: PipelineBlock | null = null;
  let bestLen = 0;
  for (const b of blocks) {
    const hay = (b.text ?? "").toLowerCase().replace(/\s+/g, " ");
    if (hay.includes(n) && n.length > bestLen) {
      best = b;
      bestLen = n.length;
    }
  }
  return best;
}

function bboxAreaFromArray(b: number[]): number {
  if (b.length < 4) return 0;
  return Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
}

/** Re-anchor candidates when stored bbox points at the wrong layout block (e.g. header b0). */
export function alignCandidateBboxes(
  candidates: PipelineCandidate[],
  blocks: PipelineBlock[],
): PipelineCandidate[] {
  if (blocks.length === 0) return candidates;
  const byId = new Map(blocks.map((b) => [b.id, b]));
  return candidates.map((c) => {
    const currentArea = isValidBbox(c.bbox) ? bboxAreaFromArray(c.bbox) : Infinity;
    // Backend already refined tight bboxes — do not expand to whole layout blocks.
    if (currentArea < 2500) return c;

    const evidence = (c.evidence_text ?? "").trim();
    const valueNeedle = c.value === null || c.value === undefined ? "" : String(c.value);
    const match =
      findBlockForNeedle(blocks, evidence) ??
      findBlockForNeedle(blocks, valueNeedle);
    if (!match || !isValidBbox(match.bbox)) {
      const cited = c.block_id ? byId.get(c.block_id) : undefined;
      if (cited && isValidBbox(cited.bbox)) return c;
      return c;
    }
    const matchArea = bboxAreaFromArray(match.bbox);
    if (matchArea >= currentArea) return c;
    return {
      ...c,
      block_id: match.id,
      page: typeof match.page === "number" && match.page > 0 ? match.page : c.page,
      bbox: match.bbox as [number, number, number, number],
    };
  });
}

const SOURCE_PRIORITY: Record<string, number> = {
  llm_context: 5,
  regex: 4,
  layout: 3,
  llm: 2,
  vision: 1,
};

function valuesEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 0.001;
  return String(a) === String(b);
}

/**
 * One highlight per resolved field (avoids painting every regex hit on the PDF).
 * Ambiguous fields still show all conflicting candidates.
 */
function dedupeCandidatesByValue(cands: PipelineCandidate[]): PipelineCandidate[] {
  const seen = new Set<string>();
  const out: PipelineCandidate[] = [];
  for (const c of cands) {
    const key = `${String(c.value).toLowerCase()}::${c.block_id ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}

export function pickDisplayCandidates(
  candidates: PipelineCandidate[],
  report: ValidateDocumentResponse,
): PipelineCandidate[] {
  const amb = new Set((report.ambiguous_fields ?? []).map((a) => a.field));
  const byField = new Map<string, PipelineCandidate[]>();
  for (const c of candidates) {
    const list = byField.get(c.field) ?? [];
    list.push(c);
    byField.set(c.field, list);
  }
  const out: PipelineCandidate[] = [];
  for (const [, rawCands] of byField) {
    const field = rawCands[0]?.field;
    if (!field) continue;
    const cands = dedupeCandidatesByValue(rawCands);
    if (amb.has(field)) {
      const distinct = new Set(cands.map((c) => String(c.value)));
      out.push(...(distinct.size > 1 ? cands : cands.slice(0, 1)));
      continue;
    }
    const resolved = report.resolved_values?.[field];
    const pool =
      resolved !== undefined && resolved !== null
        ? cands.filter((c) => valuesEqual(c.value, resolved))
        : cands;
    const sorted = [...(pool.length > 0 ? pool : cands)].sort(
      (a, b) =>
        (SOURCE_PRIORITY[(b.source ?? "").toLowerCase()] ?? 0) -
        (SOURCE_PRIORITY[(a.source ?? "").toLowerCase()] ?? 0),
    );
    if (sorted[0]) out.push(sorted[0]);
  }
  return out;
}

/** Snapshot overlays when the report has no rule ledger (typical AMBIGUOUS early exit). */
export function highlightsFromPipelineSnapshot(
  report: ValidateDocumentResponse,
  candidates: PipelineCandidate[],
  blocks: PipelineBlock[],
): PdfHighlight[] {
  const ambiguousFields = (report.ambiguous_fields ?? []).map((a) => a.field);
  if (candidates.length > 0) {
    const aligned = alignCandidateBboxes(candidates, blocks);
    const display = pickDisplayCandidates(aligned, report);
    return highlightsFromCandidates(display, { ambiguousFields });
  }
  return highlightsFromBlocks(blocks);
}

/** Layout blocks (fainter overlays) when candidates lack bbox. */
export function highlightsFromBlocks(blocks: PipelineBlock[]): PdfHighlight[] {
  const out: PdfHighlight[] = [];
  for (const b of blocks) {
    if (!isValidBbox(b.bbox)) continue;
    const page = typeof b.page === "number" && b.page > 0 ? b.page : 1;
    const preview = (b.text ?? "").trim().slice(0, 40);
    out.push({
      id: `blk-${b.id}`,
      page,
      bbox: b.bbox,
      label: preview || b.id,
      kind: "block",
    });
  }
  return dedupeHighlights(out);
}

/** Patch report outcome evidence only when stored bbox is missing or clearly too large. */
export function refineReportHighlightsWithBlocks(
  highlights: PdfHighlight[],
  blocks: PipelineBlock[],
  report: ValidateDocumentResponse,
): PdfHighlight[] {
  if (blocks.length === 0) return highlights;
  const patches = new Map<string, PdfHighlight>();
  for (const o of report.field_rule_outcomes ?? []) {
    if (!o.evidence || typeof o.evidence !== "object") continue;
    const ev = o.evidence as ValidationEvidenceOut;
    const existing = highlights.find((h) => h.field === o.field);
    const existingArea = existing ? bboxArea(existing) : Infinity;
    if (existingArea < 2500) continue;

    const needle = (ev.text ?? "").trim();
    const match = findBlockForNeedle(blocks, needle);
    if (!match || !isValidBbox(match.bbox)) continue;
    const matchArea = bboxAreaFromArray(match.bbox);
    if (matchArea >= existingArea) continue;

    const page = typeof match.page === "number" && match.page > 0 ? match.page : 1;
    patches.set(o.field, {
      id: `refined-${o.field}-${o.rule}`,
      page,
      bbox: match.bbox as [number, number, number, number],
      label: `${o.field} · ${o.rule}`,
      kind: o.passed ? "field" : "error",
      field: o.field,
      rule: o.rule,
    });
  }
  if (patches.size === 0) return highlights;
  const patchedFields = new Set(patches.keys());
  const rest = highlights.filter((h) => !h.field || !patchedFields.has(h.field));
  return dedupeHighlights([...rest, ...patches.values()]);
}

/** Merge report evidence with optional snapshot candidates/blocks. */
export function mergeHighlights(
  primary: PdfHighlight[],
  extras: PdfHighlight[],
  opts?: { includeBlocks?: boolean },
): PdfHighlight[] {
  const merged = dedupeHighlights([...primary, ...extras]);
  if (!opts?.includeBlocks) {
    return merged.filter((h) => h.kind !== "block");
  }
  return merged;
}

const HIGHLIGHT_KIND_PRIORITY: Record<HighlightKind, number> = {
  error: 4,
  field: 3,
  ambiguous: 2,
  candidate: 2,
  block: 1,
};

function bboxArea(h: PdfHighlight): number {
  const [x0, y0, x1, y1] = h.bbox;
  return Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
}

function dedupeHighlights(items: PdfHighlight[]): PdfHighlight[] {
  // One highlight per field — prefer tightest bbox (precise evidence) then higher kind priority.
  const byField = new Map<string, PdfHighlight>();
  for (const h of items) {
    const fieldKey = h.field ?? `__${h.id}`;
    const existing = byField.get(fieldKey);
    if (!existing) {
      byField.set(fieldKey, h);
      continue;
    }
    const tighter = bboxArea(h) < bboxArea(existing) * 0.95;
    const higherKind =
      HIGHLIGHT_KIND_PRIORITY[h.kind] > HIGHLIGHT_KIND_PRIORITY[existing.kind];
    if (tighter || (bboxArea(h) <= bboxArea(existing) * 1.05 && higherKind)) {
      byField.set(fieldKey, h);
    }
  }
  return [...byField.values()];
}

export function pageNumbersFromHighlights(highlights: PdfHighlight[]): number[] {
  const pages = new Set(highlights.map((h) => h.page));
  if (pages.size === 0) return [1];
  return [...pages].sort((a, b) => a - b);
}
