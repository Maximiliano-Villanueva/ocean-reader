/**
 * Parse and mutate validation schema JSON bodies for Schema Studio.
 */

export type StrictFieldSpec = {
  type: string;
  required?: boolean;
  aliases?: string[];
  regex_hint?: string;
  min?: number;
  max?: number;
  on_ambiguity?: string;
  semantic_role?: string;
  llm_fallback?: boolean;
  extraction_hint?: string;
};

export type OpenEndedSpec = {
  extract_prompt: string;
  evaluate_prompt?: string;
  informative_only?: boolean;
  link_evidence?: boolean;
  depends_on_fields?: string[];
  evaluation_tags?: string[];
};

export type ExtractionSettings = {
  understand_document?: boolean;
  context_pass?: string;
  judge_non_regex?: boolean;
  read_images?: boolean;
};

export type CrossFieldRule = {
  id: string;
  expression: string;
  error_message: string;
  fields: string[];
};

export type RepeatingGroupSpec = {
  section_hint: string;
  structure_hint: string;
  row_fields: Record<string, { type: string }>;
  row_rules?: Array<{ id: string; expression: string; error_message: string }>;
};

/** Parse editor JSON; returns null when invalid. */
export function parseSchemaJsonText(jsonText: string): Record<string, unknown> | null {
  try {
    const o = JSON.parse(jsonText) as unknown;
    return o && typeof o === "object" && !Array.isArray(o) ? (o as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function stringifySchemaBody(body: Record<string, unknown>): string {
  return JSON.stringify(body, null, 2);
}

export function getFieldsMap(body: Record<string, unknown>): Record<string, StrictFieldSpec> {
  const raw = body.fields;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return raw as Record<string, StrictFieldSpec>;
}

export function getOpenEndedMap(body: Record<string, unknown>): Record<string, OpenEndedSpec> {
  const raw = body.open_ended;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return raw as Record<string, OpenEndedSpec>;
}

export function getExtractionSettings(body: Record<string, unknown>): ExtractionSettings {
  const raw = body.extraction;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { understand_document: true, context_pass: "when_needed" };
  }
  return raw as ExtractionSettings;
}

export function getGlobalRules(body: Record<string, unknown>): string[] {
  return Array.isArray(body.rules) ? body.rules.filter((r): r is string => typeof r === "string") : [];
}

export function setFieldsMap(
  body: Record<string, unknown>,
  fields: Record<string, StrictFieldSpec>,
): Record<string, unknown> {
  return { ...body, fields };
}

export function setOpenEndedMap(
  body: Record<string, unknown>,
  openEnded: Record<string, OpenEndedSpec>,
): Record<string, unknown> {
  return { ...body, open_ended: openEnded };
}

export function updateStrictField(
  body: Record<string, unknown>,
  name: string,
  patch: Partial<StrictFieldSpec>,
): Record<string, unknown> {
  const fields = { ...getFieldsMap(body) };
  fields[name] = { ...fields[name], type: fields[name]?.type ?? "string", ...patch };
  return setFieldsMap(body, fields);
}

export function renameStrictField(
  body: Record<string, unknown>,
  oldName: string,
  newName: string,
): Record<string, unknown> {
  const trimmed = newName.trim();
  if (!trimmed || trimmed === oldName) return body;
  const fields = { ...getFieldsMap(body) };
  if (fields[trimmed]) return body;
  fields[trimmed] = fields[oldName];
  delete fields[oldName];
  return setFieldsMap(body, fields);
}

export function addStrictField(body: Record<string, unknown>, name: string): Record<string, unknown> {
  const key = name.trim() || `field_${Object.keys(getFieldsMap(body)).length + 1}`;
  const fields = { ...getFieldsMap(body) };
  if (fields[key]) return body;
  fields[key] = { type: "string", required: false, aliases: [] };
  return setFieldsMap(body, fields);
}

export function removeStrictField(body: Record<string, unknown>, name: string): Record<string, unknown> {
  const fields = { ...getFieldsMap(body) };
  delete fields[name];
  return setFieldsMap(body, fields);
}

export function updateOpenEndedField(
  body: Record<string, unknown>,
  name: string,
  patch: Partial<OpenEndedSpec>,
): Record<string, unknown> {
  const oe = { ...getOpenEndedMap(body) };
  oe[name] = { ...{ extract_prompt: "" }, ...oe[name], ...patch };
  return setOpenEndedMap(body, oe);
}

export function addOpenEndedField(body: Record<string, unknown>, name: string): Record<string, unknown> {
  const key = name.trim() || `insight_${Object.keys(getOpenEndedMap(body)).length + 1}`;
  const oe = { ...getOpenEndedMap(body) };
  if (oe[key]) return body;
  oe[key] = { extract_prompt: "", informative_only: true, link_evidence: true };
  return setOpenEndedMap(body, oe);
}

export function removeOpenEndedField(body: Record<string, unknown>, name: string): Record<string, unknown> {
  const oe = { ...getOpenEndedMap(body) };
  delete oe[name];
  return setOpenEndedMap(body, oe);
}

export function setExtractionSettings(
  body: Record<string, unknown>,
  settings: ExtractionSettings,
): Record<string, unknown> {
  return { ...body, extraction: settings };
}

export function setGlobalRules(body: Record<string, unknown>, rules: string[]): Record<string, unknown> {
  return { ...body, rules };
}

export function getCrossFieldRules(body: Record<string, unknown>): CrossFieldRule[] {
  const raw = body.cross_field_rules;
  if (!Array.isArray(raw)) return [];
  const out: CrossFieldRule[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    out.push({
      id: String(o.id ?? "rule"),
      expression: String(o.expression ?? ""),
      error_message: String(o.error_message ?? ""),
      fields: Array.isArray(o.fields) ? o.fields.map(String) : [],
    });
  }
  return out;
}

export function setCrossFieldRules(body: Record<string, unknown>, rules: CrossFieldRule[]): Record<string, unknown> {
  return { ...body, version: body.version ?? "3", cross_field_rules: rules };
}

export function getRepeatingGroups(body: Record<string, unknown>): Record<string, RepeatingGroupSpec> {
  const raw = body.groups;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return raw as Record<string, RepeatingGroupSpec>;
}

export function setRepeatingGroups(
  body: Record<string, unknown>,
  groups: Record<string, RepeatingGroupSpec>,
): Record<string, unknown> {
  return { ...body, version: body.version ?? "3", groups };
}

/** Aliases as newline-separated text for textareas. */
export function aliasesToText(aliases: string[] | undefined): string {
  return (aliases ?? []).join("\n");
}

export function textToAliases(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export type SchemaValidationFeedback = {
  dsl_ok: boolean;
  dsl_errors: string[];
  preview_status?: string | null;
  preview_summary?: string | null;
  judge_summary?: string | null;
  judge_recommendations?: string[];
};

export type SchemaJudgeFeedback = {
  summary: string;
  recommendations: string[];
  priority: string;
};

/** Build payload for schema agent from DSL + optional preview response. */
export function buildAgentValidationFeedback(
  dsl: { ok: boolean; errors: string[] },
  preview?: { status: string; summary: string } | null,
  judge?: SchemaJudgeFeedback | null,
): SchemaValidationFeedback {
  return {
    dsl_ok: dsl.ok,
    dsl_errors: dsl.errors,
    preview_status: preview?.status ?? null,
    preview_summary: preview?.summary ?? null,
    judge_summary: judge?.summary ?? null,
    judge_recommendations: judge?.recommendations ?? [],
  };
}

/** Human-readable preview summary for the agent. */
export function summarizePreviewForAgent(
  status: string,
  resolved: Record<string, unknown> | undefined,
  results: { field: string; rule: string }[],
  ambiguous: { field: string; candidate_count: number }[],
  openEnded: { field: string; evaluation?: string | null; informative_only?: boolean; extracted_value?: string | null }[],
): string {
  const lines: string[] = [`Outcome: ${status}`];
  if (resolved && Object.keys(resolved).length) {
    lines.push(
      `Resolved: ${Object.entries(resolved)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ")}`,
    );
  }
  if (results.length) {
    lines.push(`Failures: ${results.map((e) => `${e.field} (${e.rule})`).join(", ")}`);
  }
  if (ambiguous.length) {
    lines.push(
      `Ambiguous: ${ambiguous.map((a) => `${a.field} (${a.candidate_count})`).join(", ")}`,
    );
  }
  if (openEnded.length) {
    lines.push(
      `Open-ended: ${openEnded
        .map((o) => {
          if (o.informative_only) return `${o.field}=informative ${JSON.stringify(o.extracted_value)}`;
          return `${o.field}=${o.evaluation ?? "?"}`;
        })
        .join("; ")}`,
    );
  }
  return lines.join("\n");
}
