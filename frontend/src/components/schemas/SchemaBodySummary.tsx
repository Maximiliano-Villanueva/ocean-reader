/**
 * Card-style summary of a validation schema body (fields, rules, M3 extras).
 */

import type { SchemaBodySummary as Summary } from "../../lib/schemaSummary";

export type SchemaBodySummaryProps = {
  summary: Summary;
  compact?: boolean;
};

export default function SchemaBodySummaryView({ summary, compact = false }: SchemaBodySummaryProps) {
  const { fields, rules, crossFieldRules, groups, version } = summary;

  return (
    <div className={`schema-summary ${compact ? "schema-summary--compact" : ""}`.trim()}>
      <p className="schema-summary-meta muted small">
        DSL version <strong>{version}</strong>
        {" · "}
        {fields.length} field{fields.length === 1 ? "" : "s"}
        {rules.length > 0 ? ` · ${rules.length} global rule${rules.length === 1 ? "" : "s"}` : ""}
        {crossFieldRules.length > 0
          ? ` · ${crossFieldRules.length} cross-field`
          : ""}
        {groups.length > 0 ? ` · ${groups.length} repeating group${groups.length === 1 ? "" : "s"}` : ""}
      </p>

      {fields.length > 0 ? (
        <div className="schema-summary-section">
          <h4 className="schema-summary-heading">Fields</h4>
          <ul className="schema-field-cards">
            {fields.map((f) => (
              <li key={f.name} className="schema-field-card">
                <span className="schema-field-card-name">{f.name}</span>
                <span className="schema-field-card-meta muted small">
                  {f.type}
                  {f.required ? " · required" : " · optional"}
                  {f.min != null || f.max != null
                    ? ` · ${f.min ?? "…"} – ${f.max ?? "…"}`
                    : ""}
                  {f.aliasCount > 0 ? ` · ${f.aliasCount} alias${f.aliasCount === 1 ? "" : "es"}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {rules.length > 0 ? (
        <div className="schema-summary-section">
          <h4 className="schema-summary-heading">Global rules</h4>
          <p className="schema-rule-chips">
            {rules.map((r) => (
              <span key={r} className="schema-chip">
                {r}
              </span>
            ))}
          </p>
        </div>
      ) : null}

      {crossFieldRules.length > 0 ? (
        <div className="schema-summary-section">
          <h4 className="schema-summary-heading">Cross-field rules</h4>
          <ul className="schema-rule-cards">
            {crossFieldRules.map((cf) => (
              <li key={cf.id} className="schema-rule-card">
                <span className="schema-rule-card-id">{cf.id}</span>
                <code className="schema-rule-card-expr">{cf.expression}</code>
                <span className="muted tiny">Fields: {cf.fields.join(", ") || "—"}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {groups.length > 0 ? (
        <div className="schema-summary-section">
          <h4 className="schema-summary-heading">Repeating groups</h4>
          <ul className="schema-rule-cards">
            {groups.map((g) => (
              <li key={g.key} className="schema-rule-card">
                <span className="schema-rule-card-id">{g.key}</span>
                <span className="muted small">
                  Section “{g.sectionHint || "—"}” · {g.structureHint} · rows:{" "}
                  {g.rowFieldNames.join(", ") || "—"}
                  {g.rowRuleCount > 0 ? ` · ${g.rowRuleCount} row rule(s)` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
