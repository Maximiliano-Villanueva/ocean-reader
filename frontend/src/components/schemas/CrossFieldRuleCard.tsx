/**
 * Visual editor for one cross-field validation rule.
 */

import { SCHEMA_HELP } from "../../lib/schemaHelp";
import type { CrossFieldRule } from "../../lib/schemaModel";

export type CrossFieldRuleCardProps = {
  rule: CrossFieldRule;
  index: number;
  projectId: string;
  disabled?: boolean;
  onChange: (patch: Partial<CrossFieldRule>) => void;
  onRemove: () => void;
  onSuggest?: (nl: string, fields: string[]) => void;
};

function HelpTip({ text }: { text: string }) {
  return (
    <span className="schema-help-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

export default function CrossFieldRuleCard({
  rule,
  disabled,
  onChange,
  onRemove,
  onSuggest,
}: CrossFieldRuleCardProps) {
  return (
    <article className="schema-rule-card-editor schema-rule-card-editor--cross">
      <header className="schema-rule-card-editor-header">
        <span className="schema-rule-card-id">Cross-field rule</span>
        <button type="button" className="btn-ghost btn-sm schema-remove-btn" disabled={disabled} onClick={onRemove}>
          Remove
        </button>
      </header>
      <div className="schema-rule-card-editor-grid">
        <label className="field-label">
          <span>Rule id</span>
          <input
            value={rule.id}
            disabled={disabled}
            spellCheck={false}
            onChange={(e) => onChange({ id: e.target.value })}
          />
        </label>
        <label className="field-label schema-field-full">
          <span>
            Expression <HelpTip text={SCHEMA_HELP.crossFieldExpression} />
          </span>
          <input
            value={rule.expression}
            disabled={disabled}
            spellCheck={false}
            placeholder="quality >= 5 OR alcohol < 12"
            onChange={(e) => onChange({ expression: e.target.value })}
          />
        </label>
        <label className="field-label schema-field-full">
          <span>Error message</span>
          <input
            value={rule.error_message}
            disabled={disabled}
            spellCheck={false}
            onChange={(e) => onChange({ error_message: e.target.value })}
          />
        </label>
        <label className="field-label schema-field-full">
          <span>
            Fields <HelpTip text={SCHEMA_HELP.crossFieldFields} />
          </span>
          <input
            value={rule.fields.join(", ")}
            disabled={disabled}
            spellCheck={false}
            onChange={(e) =>
              onChange({
                fields: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
        {onSuggest ? (
          <div className="schema-field-full schema-m3-llm-row">
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={disabled || rule.fields.length === 0}
              onClick={() => onSuggest(rule.expression, rule.fields)}
            >
              Suggest expression (LLM)
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}
