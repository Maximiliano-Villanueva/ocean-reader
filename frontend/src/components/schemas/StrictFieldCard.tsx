/**
 * Visual editor card for one deterministic (strict) schema field.
 */

import {
  FIELD_TYPE_OPTIONS,
  ON_AMBIGUITY_OPTIONS,
  SCHEMA_HELP,
  SEMANTIC_ROLE_OPTIONS,
} from "../../lib/schemaHelp";
import type { StrictFieldSpec } from "../../lib/schemaModel";
import { aliasesToText, textToAliases } from "../../lib/schemaModel";
import EditableNameInput from "./EditableNameInput";

export type StrictFieldCardProps = {
  name: string;
  spec: StrictFieldSpec;
  disabled?: boolean;
  onChange: (patch: Partial<StrictFieldSpec>) => void;
  onRename: (newName: string) => void;
  onRemove: () => void;
};

function HelpTip({ text }: { text: string }) {
  return (
    <span className="schema-help-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

export default function StrictFieldCard({
  name,
  spec,
  disabled,
  onChange,
  onRename,
  onRemove,
}: StrictFieldCardProps) {
  const isNumber = spec.type === "number";
  const isDate = spec.type === "date";

  return (
    <article className="schema-rule-card-editor schema-rule-card-editor--strict">
      <header className="schema-rule-card-editor-header">
        <EditableNameInput
          name={name}
          disabled={disabled}
          label={
            <>
              Field ID <HelpTip text={SCHEMA_HELP.fieldName} />
            </>
          }
          onRename={onRename}
        />
        <button type="button" className="btn-ghost btn-sm schema-remove-btn" disabled={disabled} onClick={onRemove}>
          Remove
        </button>
      </header>

      <div className="schema-rule-card-editor-grid">
        <label className="field-label">
          <span>
            Type <HelpTip text={SCHEMA_HELP.fieldType} />
          </span>
          <select
            value={spec.type || "string"}
            disabled={disabled}
            onChange={(e) => onChange({ type: e.target.value })}
          >
            {FIELD_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={Boolean(spec.required)}
            disabled={disabled}
            onChange={(e) => onChange({ required: e.target.checked })}
          />
          <span>
            Required <HelpTip text={SCHEMA_HELP.required} />
          </span>
        </label>

        <label className="field-label schema-field-full">
          <span>
            PDF labels <HelpTip text={SCHEMA_HELP.aliases} />
          </span>
          <textarea
            rows={3}
            value={aliasesToText(spec.aliases)}
            disabled={disabled}
            placeholder={"Invoice number\nNº factura"}
            onChange={(e) => onChange({ aliases: textToAliases(e.target.value) })}
          />
        </label>

        <label className="field-label schema-field-full">
          <span>
            Value pattern (regex) <HelpTip text={SCHEMA_HELP.regexHint} />
          </span>
          <input
            value={spec.regex_hint ?? ""}
            disabled={disabled}
            spellCheck={false}
            placeholder="INV-\\d+"
            onChange={(e) => onChange({ regex_hint: e.target.value || undefined })}
          />
        </label>

        {isNumber ? (
          <>
            <label className="field-label">
              <span>
                Min <HelpTip text={SCHEMA_HELP.minMax} />
              </span>
              <input
                type="number"
                value={spec.min ?? ""}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ min: e.target.value === "" ? undefined : Number(e.target.value) })
                }
              />
            </label>
            <label className="field-label">
              <span>
                Max <HelpTip text={SCHEMA_HELP.minMax} />
              </span>
              <input
                type="number"
                value={spec.max ?? ""}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ max: e.target.value === "" ? undefined : Number(e.target.value) })
                }
              />
            </label>
          </>
        ) : null}

        <label className="field-label">
          <span>
            When PDF has duplicates <HelpTip text={SCHEMA_HELP.onAmbiguity} />
          </span>
          <select
            value={spec.on_ambiguity ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ on_ambiguity: e.target.value || undefined })}
          >
            {ON_AMBIGUITY_OPTIONS.map((o) => (
              <option key={o.value || "default"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field-label">
          <span>
            Document role <HelpTip text={SCHEMA_HELP.semanticRole} />
          </span>
          <select
            value={spec.semantic_role ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ semantic_role: e.target.value || undefined })}
          >
            {SEMANTIC_ROLE_OPTIONS.map((o) => (
              <option key={o.value || "none"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>

        {isDate ? (
          <label className="field-label schema-checkbox-label">
            <input
              type="checkbox"
              checked={Boolean(spec.llm_fallback)}
              disabled={disabled}
              onChange={(e) => onChange({ llm_fallback: e.target.checked })}
            />
            <span>
              AI date fallback <HelpTip text={SCHEMA_HELP.llmFallback} />
            </span>
          </label>
        ) : null}

        <details className="schema-field-advanced schema-field-full">
          <summary className="muted small">AI hint (optional)</summary>
          <label className="field-label">
            <span>
              What to look for <HelpTip text={SCHEMA_HELP.extractionHint} />
            </span>
            <textarea
              rows={2}
              value={spec.extraction_hint ?? ""}
              disabled={disabled}
              onChange={(e) => onChange({ extraction_hint: e.target.value || undefined })}
            />
          </label>
        </details>
      </div>
    </article>
  );
}
