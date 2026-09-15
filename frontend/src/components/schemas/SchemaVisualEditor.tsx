/**
 * Tabbed visual editor for strict fields, open-ended rules, cross-field, repeating groups, settings.
 */

import { useState } from "react";

import { api } from "../../api";
import { useStableEntityKeys } from "../../hooks/useStableEntityKeys";
import { GLOBAL_RULE_OPTIONS, SCHEMA_HELP } from "../../lib/schemaHelp";
import { appendM3RepeatingGroupFromForm, type M3GroupStructure } from "../../lib/schemaM3Snippets";
import {
  addOpenEndedField,
  addStrictField,
  getCrossFieldRules,
  getExtractionSettings,
  getFieldsMap,
  getGlobalRules,
  getOpenEndedMap,
  getRepeatingGroups,
  removeOpenEndedField,
  removeStrictField,
  renameStrictField,
  setCrossFieldRules,
  setExtractionSettings,
  setGlobalRules,
  setRepeatingGroups,
  stringifySchemaBody,
  updateOpenEndedField,
  updateStrictField,
  type CrossFieldRule,
  type RepeatingGroupSpec,
} from "../../lib/schemaModel";
import CrossFieldRuleCard from "./CrossFieldRuleCard";
import OpenEndedFieldCard from "./OpenEndedFieldCard";
import RepeatingGroupCard from "./RepeatingGroupCard";
import StrictFieldCard from "./StrictFieldCard";

export type SchemaVisualEditorProps = {
  projectId: string;
  body: Record<string, unknown>;
  disabled?: boolean;
  onBodyChange: (body: Record<string, unknown>) => void;
  onError?: (message: string) => void;
  /** When set with ``singleTab``, show only one section (simple cards mode). */
  initialTab?: StudioTab;
  singleTab?: boolean;
};

type StudioTab = "strict" | "prompt" | "cross" | "groups" | "settings";

function HelpTip({ text }: { text: string }) {
  return (
    <span className="schema-help-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

export default function SchemaVisualEditor({
  projectId,
  body,
  disabled,
  onBodyChange,
  onError,
  initialTab = "strict",
  singleTab = false,
}: SchemaVisualEditorProps) {
  const [tab, setTab] = useState<StudioTab>(initialTab);
  const activeTab = singleTab ? initialTab : tab;
  const { keyFor, transferKey, removeKey } = useStableEntityKeys();
  const fields = getFieldsMap(body);
  const openEnded = getOpenEndedMap(body);
  const extraction = getExtractionSettings(body);
  const globalRules = getGlobalRules(body);
  const crossRules = getCrossFieldRules(body);
  const groups = getRepeatingGroups(body);

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
      const idx = rules.findIndex((r) => r.fields.join() === fieldNames.join());
      const next: CrossFieldRule = {
        id: out.id,
        expression: out.expression,
        error_message: out.error_message,
        fields: fieldNames,
      };
      if (idx >= 0) {
        rules[idx] = { ...rules[idx], ...next };
      } else {
        rules.push(next);
      }
      patch((b) => setCrossFieldRules(b, rules));
    } catch (e: unknown) {
      onError?.(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="schema-visual-editor">
      {!singleTab ? (
        <nav className="schema-studio-tabs" aria-label="Schema sections">
          {(
            [
              ["strict", `Strict (${Object.keys(fields).length})`],
              ["prompt", `Prompt (${Object.keys(openEnded).length})`],
              ["cross", `Cross-field (${crossRules.length})`],
              ["groups", `Tables (${Object.keys(groups).length})`],
              ["settings", "Settings"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`schema-studio-tab ${activeTab === id ? "schema-studio-tab--active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      ) : null}

      {activeTab === "strict" ? (
        <section className="schema-visual-section">
          <p className="muted small schema-section-lead">{SCHEMA_HELP.strictIntro}</p>
          <div className="schema-visual-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={disabled}
              onClick={() => patch((b) => addStrictField(b, ""))}
            >
              Add strict field
            </button>
          </div>
          <div className="schema-rule-card-list">
            {Object.entries(fields).map(([name, spec]) => (
              <StrictFieldCard
                key={keyFor(name, "strict")}
                name={name}
                spec={spec}
                disabled={disabled}
                onChange={(p) => patch((b) => updateStrictField(b, name, p))}
                onRename={(newName) => {
                  transferKey(name, newName);
                  patch((b) => renameStrictField(b, name, newName));
                }}
                onRemove={() => {
                  removeKey(name);
                  patch((b) => removeStrictField(b, name));
                }}
              />
            ))}
            {Object.keys(fields).length === 0 ? (
              <p className="muted small">No strict fields yet. Add one or ask the assistant.</p>
            ) : null}
          </div>
        </section>
      ) : null}

      {activeTab === "prompt" ? (
        <section className="schema-visual-section">
          <p className="muted small schema-section-lead">{SCHEMA_HELP.openEndedIntro}</p>
          <div className="schema-visual-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={disabled}
              onClick={() => patch((b) => addOpenEndedField(b, ""))}
            >
              Add prompt rule
            </button>
          </div>
          <div className="schema-rule-card-list">
            {Object.entries(openEnded).map(([name, spec]) => (
              <OpenEndedFieldCard
                key={keyFor(name, "prompt")}
                name={name}
                spec={spec}
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
                  patch((b) => removeOpenEndedField(b, name));
                }}
              />
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "cross" ? (
        <section className="schema-visual-section">
          <p className="muted small schema-section-lead">{SCHEMA_HELP.crossFieldIntro}</p>
          <div className="schema-visual-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={disabled}
              onClick={() =>
                patch((b) =>
                  setCrossFieldRules(b, [
                    ...getCrossFieldRules(b),
                    {
                      id: `rule_${getCrossFieldRules(b).length + 1}`,
                      expression: "",
                      error_message: "Rule failed",
                      fields: [],
                    },
                  ]),
                )
              }
            >
              Add cross-field rule
            </button>
          </div>
          <div className="schema-rule-card-list">
            {crossRules.map((rule, i) => (
              <CrossFieldRuleCard
                key={keyFor(`cross-${i}`, "cross")}
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
                onSuggest={(nl, fields) => void suggestCrossField(nl, fields)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "groups" ? (
        <section className="schema-visual-section">
          <p className="muted small schema-section-lead">{SCHEMA_HELP.repeatingIntro}</p>
          <div className="schema-visual-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={disabled}
              onClick={() => {
                const text = appendM3RepeatingGroupFromForm(stringifySchemaBody(body), {
                  groupKey: `group_${Object.keys(groups).length + 1}`,
                  sectionHint: "Section title",
                  structureHint: "list" as M3GroupStructure,
                  rowRuleId: "within_spec",
                  rowExpression: "true",
                  rowErrorMessage: "Row failed",
                });
                onBodyChange(JSON.parse(text) as Record<string, unknown>);
              }}
            >
              Add repeating group
            </button>
          </div>
          <div className="schema-rule-card-list">
            {Object.entries(groups).map(([key, spec]) => (
              <RepeatingGroupCard
                key={keyFor(key, "group")}
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
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "settings" ? (
        <section className="schema-visual-section">
          <h4 className="schema-visual-subheading">
            Document understanding <HelpTip text={SCHEMA_HELP.documentUnderstanding} />
          </h4>
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
              Contextual pass <HelpTip text={SCHEMA_HELP.contextPass} />
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
            <span>
              LLM judge non-regex extractions <HelpTip text={SCHEMA_HELP.judgeNonRegex} />
            </span>
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
            <span>
              Read images <HelpTip text={SCHEMA_HELP.readImages} />
            </span>
          </label>

          <h4 className="schema-visual-subheading">
            Global rules <HelpTip text={SCHEMA_HELP.globalRules} />
          </h4>
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
        </section>
      ) : null}
    </div>
  );
}
