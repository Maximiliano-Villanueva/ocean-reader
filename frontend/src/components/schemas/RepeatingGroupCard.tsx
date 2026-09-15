/**
 * Visual editor for one repeating group (table/list section).
 */

import { SCHEMA_HELP } from "../../lib/schemaHelp";
import type { M3GroupStructure } from "../../lib/schemaM3Snippets";
import type { RepeatingGroupSpec } from "../../lib/schemaModel";
import EditableNameInput from "./EditableNameInput";

export type RepeatingGroupCardProps = {
  groupKey: string;
  spec: RepeatingGroupSpec;
  disabled?: boolean;
  onRename: (key: string) => void;
  onChange: (patch: Partial<RepeatingGroupSpec>) => void;
  onRemove: () => void;
};

function HelpTip({ text }: { text: string }) {
  return (
    <span className="schema-help-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

export default function RepeatingGroupCard({
  groupKey,
  spec,
  disabled,
  onRename,
  onChange,
  onRemove,
}: RepeatingGroupCardProps) {
  const rowRule = spec.row_rules?.[0];

  return (
    <article className="schema-rule-card-editor schema-rule-card-editor--group">
      <header className="schema-rule-card-editor-header">
        <EditableNameInput name={groupKey} disabled={disabled} label="Group key" onRename={onRename} />
        <button type="button" className="btn-ghost btn-sm schema-remove-btn" disabled={disabled} onClick={onRemove}>
          Remove
        </button>
      </header>
      <div className="schema-rule-card-editor-grid">
        <label className="field-label schema-field-full">
          <span>
            Section in PDF <HelpTip text={SCHEMA_HELP.repeatingSection} />
          </span>
          <input
            value={spec.section_hint ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ section_hint: e.target.value })}
          />
        </label>
        <label className="field-label">
          <span>
            Layout <HelpTip text={SCHEMA_HELP.repeatingStructure} />
          </span>
          <select
            value={spec.structure_hint ?? "list"}
            disabled={disabled}
            onChange={(e) => onChange({ structure_hint: e.target.value as M3GroupStructure })}
          >
            <option value="list">List</option>
            <option value="table">Table</option>
            <option value="sections">Sections</option>
          </select>
        </label>
        {rowRule ? (
          <>
            <label className="field-label schema-field-full">
              <span>Row rule expression</span>
              <input
                value={rowRule.expression}
                disabled={disabled}
                spellCheck={false}
                onChange={(e) =>
                  onChange({
                    row_rules: [{ ...rowRule, expression: e.target.value }],
                  })
                }
              />
            </label>
            <label className="field-label schema-field-full">
              <span>Row error message</span>
              <input
                value={rowRule.error_message}
                disabled={disabled}
                spellCheck={false}
                onChange={(e) =>
                  onChange({
                    row_rules: [{ ...rowRule, error_message: e.target.value }],
                  })
                }
              />
            </label>
          </>
        ) : null}
        <p className="muted tiny schema-field-full">
          Row fields use the standard wine table template (parameter, measured_value, bounds). Edit JSON for custom
          columns.
        </p>
      </div>
    </article>
  );
}
