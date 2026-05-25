/**
 * Human-readable summaries of validation schema JSON bodies for the schemas UI.
 */

export type SchemaFieldSummary = {
  name: string;
  type: string;
  required: boolean;
  min?: number;
  max?: number;
  aliasCount: number;
};

export type SchemaCrossFieldSummary = {
  id: string;
  expression: string;
  fields: string[];
  errorMessage: string;
};

export type SchemaGroupSummary = {
  key: string;
  sectionHint: string;
  structureHint: string;
  rowFieldNames: string[];
  rowRuleCount: number;
};

export type SchemaBodySummary = {
  version: string;
  fields: SchemaFieldSummary[];
  rules: string[];
  crossFieldRules: SchemaCrossFieldSummary[];
  groups: SchemaGroupSummary[];
};

/** Parse a schema body object into display-friendly structures (tolerant of partial JSON). */
export function summarizeSchemaBody(body: Record<string, unknown> | null | undefined): SchemaBodySummary {
  if (!body || typeof body !== "object") {
    return { version: "1", fields: [], rules: [], crossFieldRules: [], groups: [] };
  }

  const version = typeof body.version === "string" ? body.version : String(body.version ?? "1");
  const fieldsSpec = body.fields;
  const fields: SchemaFieldSummary[] = [];
  if (fieldsSpec && typeof fieldsSpec === "object" && !Array.isArray(fieldsSpec)) {
    for (const [name, spec] of Object.entries(fieldsSpec)) {
      const s = spec && typeof spec === "object" ? (spec as Record<string, unknown>) : {};
      const aliases = s.aliases;
      fields.push({
        name,
        type: typeof s.type === "string" ? s.type : "unknown",
        required: Boolean(s.required),
        min: typeof s.min === "number" ? s.min : undefined,
        max: typeof s.max === "number" ? s.max : undefined,
        aliasCount: Array.isArray(aliases) ? aliases.length : 0,
      });
    }
  }
  fields.sort((a, b) => a.name.localeCompare(b.name));

  const rules = Array.isArray(body.rules)
    ? body.rules.filter((r): r is string => typeof r === "string")
    : [];

  const crossFieldRules: SchemaCrossFieldSummary[] = [];
  if (Array.isArray(body.cross_field_rules)) {
    for (const cf of body.cross_field_rules) {
      if (!cf || typeof cf !== "object") continue;
      const o = cf as Record<string, unknown>;
      crossFieldRules.push({
        id: String(o.id ?? "rule"),
        expression: String(o.expression ?? ""),
        fields: Array.isArray(o.fields) ? o.fields.map(String) : [],
        errorMessage: String(o.error_message ?? ""),
      });
    }
  }

  const groups: SchemaGroupSummary[] = [];
  const groupsSpec = body.groups;
  if (groupsSpec && typeof groupsSpec === "object" && !Array.isArray(groupsSpec)) {
    for (const [key, g] of Object.entries(groupsSpec)) {
      if (!g || typeof g !== "object") continue;
      const o = g as Record<string, unknown>;
      const rowFields = o.row_fields;
      const rowFieldNames =
        rowFields && typeof rowFields === "object" && !Array.isArray(rowFields)
          ? Object.keys(rowFields)
          : [];
      const rowRules = o.row_rules;
      groups.push({
        key,
        sectionHint: String(o.section_hint ?? ""),
        structureHint: String(o.structure_hint ?? "table"),
        rowFieldNames,
        rowRuleCount: Array.isArray(rowRules) ? rowRules.length : 0,
      });
    }
  }

  return { version, fields, rules, crossFieldRules, groups };
}

/** Try parsing editor text; returns ``null`` on invalid JSON. */
export function summarizeSchemaJsonText(jsonText: string): SchemaBodySummary | null {
  try {
    const o = JSON.parse(jsonText) as Record<string, unknown>;
    return summarizeSchemaBody(o);
  } catch {
    return null;
  }
}

/** Short created-at label for tables. */
export function formatSchemaTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}
