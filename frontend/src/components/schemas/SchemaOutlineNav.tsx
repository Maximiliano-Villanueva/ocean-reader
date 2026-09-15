/**
 * Left outline tree for workspace mode — replaces horizontal tabs.
 */

import { SCHEMA_UI, type SchemaOutlineSelection } from "../../lib/schemaUiLabels";
import {
  getCrossFieldRules,
  getFieldsMap,
  getOpenEndedMap,
  getRepeatingGroups,
} from "../../lib/schemaModel";

export type SchemaOutlineNavProps = {
  body: Record<string, unknown>;
  selection: SchemaOutlineSelection;
  onSelect: (sel: SchemaOutlineSelection) => void;
  onAddStrict: () => void;
  onAddOpenEnded: () => void;
  onAddCross: () => void;
  onAddGroup: () => void;
  disabled?: boolean;
};

export default function SchemaOutlineNav({
  body,
  selection,
  onSelect,
  onAddStrict,
  onAddOpenEnded,
  onAddCross,
  onAddGroup,
  disabled,
}: SchemaOutlineNavProps) {
  const fields = Object.keys(getFieldsMap(body));
  const openEnded = Object.keys(getOpenEndedMap(body));
  const cross = getCrossFieldRules(body);
  const groups = Object.keys(getRepeatingGroups(body));

  function itemClass(active: boolean): string {
    return `schema-outline-item${active ? " schema-outline-item--active" : ""}`;
  }

  function isStrictActive(name: string): boolean {
    return selection.kind === "strict" && selection.field === name;
  }

  return (
    <nav className="schema-outline" aria-label="Schema outline">
      <button
        type="button"
        className={itemClass(selection.kind === "welcome")}
        onClick={() => onSelect({ kind: "welcome" })}
      >
        Overview
      </button>

      <div className="schema-outline-group">
        <div className="schema-outline-group-head">
          <span>{SCHEMA_UI.sectionStrict}</span>
          <span className="schema-outline-count">{fields.length}</span>
        </div>
        {fields.map((name) => (
          <button
            key={name}
            type="button"
            className={itemClass(isStrictActive(name))}
            onClick={() => onSelect({ kind: "strict", field: name })}
          >
            <code>{name}</code>
          </button>
        ))}
        <button type="button" className="schema-outline-add" disabled={disabled} onClick={onAddStrict}>
          + Add field
        </button>
      </div>

      <div className="schema-outline-group">
        <div className="schema-outline-group-head">
          <span>{SCHEMA_UI.sectionOpenEnded}</span>
          <span className="schema-outline-count">{openEnded.length}</span>
        </div>
        {openEnded.map((name) => (
          <button
            key={name}
            type="button"
            className={itemClass(selection.kind === "open_ended" && selection.field === name)}
            onClick={() => onSelect({ kind: "open_ended", field: name })}
          >
            <code>{name}</code>
          </button>
        ))}
        <button type="button" className="schema-outline-add" disabled={disabled} onClick={onAddOpenEnded}>
          + Add insight
        </button>
      </div>

      <div className="schema-outline-group">
        <div className="schema-outline-group-head">
          <span>{SCHEMA_UI.sectionCross}</span>
          <span className="schema-outline-count">{cross.length}</span>
        </div>
        {cross.map((rule, i) => (
          <button
            key={`${rule.id}-${i}`}
            type="button"
            className={itemClass(selection.kind === "cross" && selection.index === i)}
            onClick={() => onSelect({ kind: "cross", index: i })}
          >
            {rule.id || `Rule ${i + 1}`}
          </button>
        ))}
        <button type="button" className="schema-outline-add" disabled={disabled} onClick={onAddCross}>
          + Add rule
        </button>
      </div>

      <div className="schema-outline-group">
        <div className="schema-outline-group-head">
          <span>{SCHEMA_UI.sectionGroups}</span>
          <span className="schema-outline-count">{groups.length}</span>
        </div>
        {groups.map((key) => (
          <button
            key={key}
            type="button"
            className={itemClass(selection.kind === "group" && selection.key === key)}
            onClick={() => onSelect({ kind: "group", key })}
          >
            <code>{key}</code>
          </button>
        ))}
        <button type="button" className="schema-outline-add" disabled={disabled} onClick={onAddGroup}>
          + Add section
        </button>
      </div>

      <button
        type="button"
        className={itemClass(selection.kind === "settings")}
        onClick={() => onSelect({ kind: "settings" })}
      >
        {SCHEMA_UI.sectionPdf}
      </button>
    </nav>
  );
}
