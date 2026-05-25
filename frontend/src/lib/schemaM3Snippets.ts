/** Milestone 3 JSON merge helpers for the schema revision editor. */

export type M3GroupStructure = "table" | "list" | "sections";

export function appendM3WineCrossFieldRule(jsonText: string): string {
  const o = JSON.parse(jsonText) as Record<string, unknown>;
  o.version = "2";
  const existing = Array.isArray(o.cross_field_rules) ? [...(o.cross_field_rules as unknown[])] : [];
  existing.push({
    id: "high_alcohol_quality",
    expression: "quality >= 5 OR alcohol < 12",
    error_message: "Wine with alcohol ≥ 12% must have quality ≥ 5 (alcohol {alcohol}, quality {quality})",
    fields: ["alcohol", "quality"],
  });
  o.cross_field_rules = existing;
  return JSON.stringify(o, null, 2);
}

export function appendM3CrossFieldFromForm(
  jsonText: string,
  opts: { id: string; expression: string; error_message: string; fieldsCsv: string },
): string {
  const o = JSON.parse(jsonText) as Record<string, unknown>;
  o.version = "2";
  const fields = opts.fieldsCsv
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const existing = Array.isArray(o.cross_field_rules) ? [...(o.cross_field_rules as unknown[])] : [];
  existing.push({
    id: opts.id.trim() || "custom_rule",
    expression: opts.expression.trim(),
    error_message: opts.error_message.trim() || "Rule failed",
    fields,
  });
  o.cross_field_rules = existing;
  return JSON.stringify(o, null, 2);
}

export function appendM3RepeatingGroupSnippet(jsonText: string): string {
  const o = JSON.parse(jsonText) as Record<string, unknown>;
  o.version = "2";
  o.groups = {
    ...((o.groups as Record<string, unknown>) || {}),
    test_results: {
      section_hint: "Test Results",
      structure_hint: "list",
      row_fields: {
        parameter: { type: "string" },
        measured_value: { type: "number" },
        lower_bound: { type: "number" },
        upper_bound: { type: "number" },
      },
      row_rules: [
        {
          id: "within_spec",
          expression: "lower_bound <= measured_value AND measured_value <= upper_bound",
          error_message: "{parameter}: measured {measured_value} outside [{lower_bound}, {upper_bound}]",
        },
      ],
    },
  };
  return JSON.stringify(o, null, 2);
}

export function appendM3RepeatingGroupFromForm(
  jsonText: string,
  opts: {
    groupKey: string;
    sectionHint: string;
    structureHint: M3GroupStructure;
    rowRuleId: string;
    rowExpression: string;
    rowErrorMessage: string;
  },
): string {
  const o = JSON.parse(jsonText) as Record<string, unknown>;
  o.version = "2";
  const gkey = opts.groupKey.trim() || "test_results";
  const row_fields = {
    parameter: { type: "string" },
    measured_value: { type: "number" },
    lower_bound: { type: "number" },
    upper_bound: { type: "number" },
  };
  const groups = { ...((o.groups as Record<string, unknown>) || {}) };
  groups[gkey] = {
    section_hint: opts.sectionHint.trim(),
    structure_hint: opts.structureHint,
    row_fields,
    row_rules: [
      {
        id: opts.rowRuleId.trim() || "row_rule",
        expression: opts.rowExpression.trim(),
        error_message: opts.rowErrorMessage.trim() || "Row rule failed",
      },
    ],
  };
  o.groups = groups;
  return JSON.stringify(o, null, 2);
}
