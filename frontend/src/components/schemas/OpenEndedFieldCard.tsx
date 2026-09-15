/**
 * Visual editor card for one open-ended (prompt-based) schema rule.
 */

import { SCHEMA_HELP } from "../../lib/schemaHelp";
import type { OpenEndedSpec } from "../../lib/schemaModel";
import EditableNameInput from "./EditableNameInput";

export type OpenEndedFieldCardProps = {
  name: string;
  spec: OpenEndedSpec;
  disabled?: boolean;
  onChange: (patch: Partial<OpenEndedSpec>) => void;
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

export default function OpenEndedFieldCard({
  name,
  spec,
  disabled,
  onChange,
  onRename,
  onRemove,
}: OpenEndedFieldCardProps) {
  const informative = Boolean(spec.informative_only);

  return (
    <article className="schema-rule-card-editor schema-rule-card-editor--open">
      <header className="schema-rule-card-editor-header">
        <EditableNameInput
          name={name}
          disabled={disabled}
          label={
            <>
              Rule name <HelpTip text={SCHEMA_HELP.fieldName} />
            </>
          }
          onRename={onRename}
        />
        <button type="button" className="btn-ghost btn-sm schema-remove-btn" disabled={disabled} onClick={onRemove}>
          Remove
        </button>
      </header>

      <div className="schema-rule-card-editor-grid">
        <label className="field-label schema-field-full">
          <span>
            What to extract <HelpTip text={SCHEMA_HELP.extractPrompt} />
          </span>
          <textarea
            rows={4}
            value={spec.extract_prompt ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ extract_prompt: e.target.value })}
            placeholder="Extract the executive summary in one paragraph…"
          />
        </label>

        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={informative}
            disabled={disabled}
            onChange={(e) => onChange({ informative_only: e.target.checked })}
          />
          <span>
            Report only (no pass/fail) <HelpTip text={SCHEMA_HELP.informativeOnly} />
          </span>
        </label>

        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={spec.link_evidence !== false}
            disabled={disabled}
            onChange={(e) => onChange({ link_evidence: e.target.checked })}
          />
          <span>
            Link PDF evidence <HelpTip text={SCHEMA_HELP.linkEvidence} />
          </span>
        </label>

        {!informative ? (
          <label className="field-label schema-field-full">
            <span>
              When is it valid? <HelpTip text={SCHEMA_HELP.evaluatePrompt} />
            </span>
            <textarea
              rows={3}
              value={spec.evaluate_prompt ?? ""}
              disabled={disabled}
              onChange={(e) => onChange({ evaluate_prompt: e.target.value || undefined })}
              placeholder="Pass if the email equals ap.demo@acme-supply.test…"
            />
          </label>
        ) : null}

        <label className="field-label schema-field-full">
          <span>
            Uses other fields <HelpTip text={SCHEMA_HELP.dependsOn} />
          </span>
          <input
            value={(spec.depends_on_fields ?? []).join(", ")}
            disabled={disabled}
            spellCheck={false}
            placeholder="invoice_number, total_usd"
            onChange={(e) =>
              onChange({
                depends_on_fields: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
      </div>
    </article>
  );
}
