/**
 * Workspace center panel — edit one outline selection at a time.
 */

import { api } from "../../api";
import { useStableEntityKeys } from "../../hooks/useStableEntityKeys";
import { GLOBAL_RULE_OPTIONS, SCHEMA_HELP } from "../../lib/schemaHelp";
import { SCHEMA_UI, type SchemaOutlineSelection } from "../../lib/schemaUiLabels";
import {
  getCrossFieldRules,
  getExtractionSettings,
  getFieldsMap,
  getGlobalRules,
  getOpenEndedMap,
  getRepeatingGroups,
  renameStrictField,
  setCrossFieldRules,
  setExtractionSettings,
  setGlobalRules,
  setRepeatingGroups,
  updateOpenEndedField,
  updateStrictField,
  type CrossFieldRule,
  type RepeatingGroupSpec,
} from "../../lib/schemaModel";
import CrossFieldRuleCard from "./CrossFieldRuleCard";
import OpenEndedFieldCard from "./OpenEndedFieldCard";
import RepeatingGroupCard from "./RepeatingGroupCard";
import StrictFieldCard from "./StrictFieldCard";

export type SchemaFocusPanelProps = {
  projectId: string;
  body: Record<string, unknown>;
  selection: SchemaOutlineSelection;
  disabled?: boolean;
  onBodyChange: (body: Record<string, unknown>) => void;
  onError?: (message: string) => void;
  onAddStrict: () => void;
};

function HelpTip({ text }: { text: string }) {
  return (
    <span className="schema-help-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

export default function SchemaFocusPanel({
  projectId,
  body,
  selection,
  disabled,
  onBodyChange,
  onError,
  onAddStrict,
}: SchemaFocusPanelProps) {
  const { keyFor, transferKey, removeKey } = useStableEntityKeys();
  const fields = getFieldsMap(body);
  const openEnded = getOpenEndedMap(body);
  const crossRules = getCrossFieldRules(body);
  const groups = getRepeatingGroups(body);
  const extraction = getExtractionSettings(body);
  const globalRules = getGlobalRules(body);

  function patch(fn: (b: Record<string, unknown>) => Record<string, unknown>) {
    onBodyChange(fn(body));
  }

  async function suggestCrossField(nl: string, fieldNames: string[]) {
    if (!projectId) return;
    try {
      const out = await api.validation.suggestCrossFieldRule(projectId, {
        natural_language: nl || "Cross-field validation",
        allowed_field_names: fieldNames,
      });
      const rules = getCrossFieldRules(body);
      const next: CrossFieldRule = {
        id: out.id,
        expression: out.expression,
        error_message: out.error_message,
        fields: fieldNames,
      };
      rules.push(next);
      patch((b) => setCrossFieldRules(b, rules));
    } catch (e: unknown) {
      onError?.(e instanceof Error ? e.message : String(e));
    }
  }

  if (selection.kind === "welcome") {
    const fieldCount = Object.keys(fields).length;
    const oeCount = Object.keys(openEnded).length;
    return (
      <div className="schema-focus-welcome">
        <h3 className="schema-focus-title">Checklist overview</h3>
        <p className="muted schema-focus-lead">
          Use the outline on the left to edit one section at a time. Upload a sample PDF on the right to
          test as you go. The assistant can add fields or fix errors in plain language.
        </p>
        <ul className="schema-focus-stats">
          <li>
            <strong>{fieldCount}</strong> fields to extract
          </li>
          <li>
            <strong>{oeCount}</strong> extra insights
          </li>
          <li>
            <strong>{crossRules.length}</strong> cross-field rules
          </li>
          <li>
            <strong>{Object.keys(groups).length}</strong> repeating sections
          </li>
        </ul>
        {fieldCount === 0 ? (
          <button type="button" className="btn-primary" disabled={disabled} onClick={onAddStrict}>
            Add your first field
          </button>
        ) : null}
      </div>
    );
  }

  if (selection.kind === "strict" && fields[selection.field]) {
    const name = selection.field;
    return (
      <div className="schema-focus-panel">
        <h3 className="schema-focus-title">{SCHEMA_UI.sectionStrict}</h3>
        <p className="muted small schema-focus-lead">{SCHEMA_UI.sectionStrictLead}</p>
        <StrictFieldCard
          key={keyFor(name, "strict")}
          name={name}
          spec={fields[name]}
          disabled={disabled}
          onChange={(p) => patch((b) => updateStrictField(b, name, p))}
          onRename={(newName) => {
            transferKey(name, newName);
            patch((b) => renameStrictField(b, name, newName));
          }}
          onRemove={() => {
            removeKey(name);
            patch((b) => {
              const map = { ...getFieldsMap(b) };
              delete map[name];
              return { ...b, fields: map };
            });
          }}
        />
      </div>
    );
  }

  if (selection.kind === "open_ended" && openEnded[selection.field]) {
    const name = selection.field;
    return (
      <div className="schema-focus-panel">
        <h3 className="schema-focus-title">{SCHEMA_UI.sectionOpenEnded}</h3>
        <p className="muted small schema-focus-lead">{SCHEMA_UI.sectionOpenEndedLead}</p>
        <OpenEndedFieldCard
          key={keyFor(name, "prompt")}
          name={name}
          spec={openEnded[name]}
          disabled={disabled}
          onChange={(p) => patch((b) => updateOpenEndedField(b, name, p))}
          onRename={(newName) => {
            transferKey(name, newName);
            patch((b) => {
              const map = { ...getOpenEndedMap(b) };
              if (map[newName]) return b;
              map[newName] = map[name];
              delete map[name];
              return { ...b, open_ended: map };
            });
          }}
          onRemove={() => {
            removeKey(name);
            patch((b) => {
              const map = { ...getOpenEndedMap(b) };
              delete map[name];
              return { ...b, open_ended: map };
            });
          }}
        />
      </div>
    );
  }

  if (selection.kind === "cross" && crossRules[selection.index]) {
    const i = selection.index;
    const rule = crossRules[i];
    return (
      <div className="schema-focus-panel">
        <h3 className="schema-focus-title">{SCHEMA_UI.sectionCross}</h3>
        <p className="muted small schema-focus-lead">{SCHEMA_UI.sectionCrossLead}</p>
        <CrossFieldRuleCard
          rule={rule}
          index={i}
          projectId={projectId}
          disabled={disabled}
          onChange={(p) => {
            const next = [...crossRules];
            next[i] = { ...next[i], ...p };
            patch((b) => setCrossFieldRules(b, next));
          }}
          onRemove={() => {
            removeKey(`cross-${i}`);
            patch((b) => setCrossFieldRules(b, crossRules.filter((_, j) => j !== i)));
          }}
          onSuggest={(nl, fieldList) => void suggestCrossField(nl, fieldList)}
        />
      </div>
    );
  }

  if (selection.kind === "group" && groups[selection.key]) {
    const key = selection.key;
    const spec = groups[key];
    return (
      <div className="schema-focus-panel">
        <h3 className="schema-focus-title">{SCHEMA_UI.sectionGroups}</h3>
        <p className="muted small schema-focus-lead">{SCHEMA_UI.sectionGroupsLead}</p>
        <RepeatingGroupCard
          groupKey={key}
          spec={spec}
          disabled={disabled}
          onChange={(p) => {
            const next = { ...groups, [key]: { ...spec, ...p } as RepeatingGroupSpec };
            patch((b) => setRepeatingGroups(b, next));
          }}
          onRename={(newKey) => {
            transferKey(key, newKey);
            const next = { ...groups };
            next[newKey] = next[key];
            delete next[key];
            patch((b) => setRepeatingGroups(b, next));
          }}
          onRemove={() => {
            removeKey(key);
            const next = { ...groups };
            delete next[key];
            patch((b) => setRepeatingGroups(b, next));
          }}
        />
      </div>
    );
  }

  if (selection.kind === "settings") {
    return (
      <div className="schema-focus-panel">
        <h3 className="schema-focus-title">{SCHEMA_UI.sectionPdf}</h3>
        <p className="muted small schema-focus-lead">{SCHEMA_UI.sectionPdfLead}</p>
        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={extraction.understand_document !== false}
            disabled={disabled}
            onChange={(e) =>
              patch((b) =>
                setExtractionSettings(b, { ...getExtractionSettings(b), understand_document: e.target.checked }),
              )
            }
          />
          <span>Understand document layout before extraction</span>
        </label>
        <label className="field-label">
          <span>
            Contextual AI pass <HelpTip text={SCHEMA_HELP.contextPass} />
          </span>
          <select
            value={extraction.context_pass ?? "when_needed"}
            disabled={disabled}
            onChange={(e) =>
              patch((b) =>
                setExtractionSettings(b, { ...getExtractionSettings(b), context_pass: e.target.value }),
              )
            }
          >
            <option value="when_needed">When needed (default)</option>
            <option value="always">Always</option>
          </select>
        </label>
        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={extraction.judge_non_regex !== false}
            disabled={disabled}
            onChange={(e) =>
              patch((b) =>
                setExtractionSettings(b, { ...getExtractionSettings(b), judge_non_regex: e.target.checked }),
              )
            }
          />
          <span>LLM judge non-regex extractions</span>
        </label>
        <label className="field-label schema-checkbox-label">
          <input
            type="checkbox"
            checked={extraction.read_images === true}
            disabled={disabled}
            onChange={(e) =>
              patch((b) =>
                setExtractionSettings(b, { ...getExtractionSettings(b), read_images: e.target.checked }),
              )
            }
          />
          <span>Read images in PDF (Docling + vision)</span>
        </label>

        <h4 className="schema-visual-subheading">{SCHEMA_UI.sectionGlobal}</h4>
        <div className="schema-global-rules">
          {GLOBAL_RULE_OPTIONS.map((opt) => (
            <label key={opt.key} className="field-label schema-checkbox-label">
              <input
                type="checkbox"
                checked={globalRules.includes(opt.key)}
                disabled={disabled}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...globalRules, opt.key]
                    : globalRules.filter((r) => r !== opt.key);
                  patch((b) => setGlobalRules(b, next));
                }}
              />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="schema-focus-welcome">
      <p className="muted">Selection not found. Pick an item from the outline.</p>
    </div>
  );
}
