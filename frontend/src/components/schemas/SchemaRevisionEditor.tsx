/**
 * Side panel: edit JSON and publish a new immutable schema revision.
 */

import { type FormEvent, useState } from "react";

import { api } from "../../api";
import {
  appendM3CrossFieldFromForm,
  appendM3RepeatingGroupFromForm,
  type M3GroupStructure,
} from "../../lib/schemaM3Snippets";
import { summarizeSchemaJsonText } from "../../lib/schemaSummary";
import SchemaBodySummaryView from "./SchemaBodySummary";

export type SchemaRevisionEditorProps = {
  projectId: string;
  schemaKey: string;
  jsonText: string;
  busy: boolean;
  onSchemaKeyChange: (key: string) => void;
  onJsonTextChange: (text: string) => void;
  onPublish: (e: FormEvent) => void;
  onCancel: () => void;
  onError: (message: string) => void;
};

export default function SchemaRevisionEditor({
  projectId,
  schemaKey,
  jsonText,
  busy,
  onSchemaKeyChange,
  onJsonTextChange,
  onPublish,
  onCancel,
  onError,
}: SchemaRevisionEditorProps) {
  const [editorTab, setEditorTab] = useState<"summary" | "json">("summary");
  const [cfRuleId, setCfRuleId] = useState("my_rule");
  const [cfExpression, setCfExpression] = useState("quality >= 5 OR alcohol < 12");
  const [cfErrorMessage, setCfErrorMessage] = useState(
    "When alcohol is high, quality must be sufficient (alcohol {alcohol}, quality {quality})",
  );
  const [cfFieldsCsv, setCfFieldsCsv] = useState("alcohol, quality");
  const [cfAssistNl, setCfAssistNl] = useState("If alcohol is at least 12%, quality must be at least 5.");
  const [rgGroupKey, setRgGroupKey] = useState("test_results");
  const [rgSectionHint, setRgSectionHint] = useState("Test Results");
  const [rgStructure, setRgStructure] = useState<M3GroupStructure>("list");
  const [rgRuleId, setRgRuleId] = useState("within_spec");
  const [rgExpression, setRgExpression] = useState(
    "lower_bound <= measured_value AND measured_value <= upper_bound",
  );
  const [rgErrorMessage, setRgErrorMessage] = useState(
    "{parameter}: measured {measured_value} outside [{lower_bound}, {upper_bound}]",
  );

  const liveSummary = summarizeSchemaJsonText(jsonText);
  const jsonInvalid = liveSummary === null;

  return (
    <form className="schema-editor-panel" onSubmit={onPublish}>
      <header className="schema-editor-panel-header">
        <h2 className="schema-editor-panel-title">New revision</h2>
        <p className="muted small">
          Based on <code>{schemaKey}</code>. Publishing creates the next label automatically (e.g. 1.0 → 1.1).
        </p>
      </header>

      <label className="field-label">
        <span>Schema key</span>
        <input value={schemaKey} onChange={(e) => onSchemaKeyChange(e.target.value)} spellCheck={false} />
      </label>

      <div className="schema-editor-tabs" role="tablist" aria-label="Editor view">
        <button
          type="button"
          role="tab"
          aria-selected={editorTab === "summary"}
          className={`schema-editor-tab ${editorTab === "summary" ? "schema-editor-tab--active" : ""}`}
          onClick={() => setEditorTab("summary")}
        >
          Summary
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={editorTab === "json"}
          className={`schema-editor-tab ${editorTab === "json" ? "schema-editor-tab--active" : ""}`}
          onClick={() => setEditorTab("json")}
        >
          JSON
        </button>
      </div>

      {editorTab === "summary" ? (
        <div className="schema-editor-summary-pane">
          {jsonInvalid ? (
            <p className="alert-error">Fix JSON syntax to see a readable summary.</p>
          ) : (
            <SchemaBodySummaryView summary={liveSummary} compact />
          )}
        </div>
      ) : (
        <label className="field-label">
          <span>Definition JSON</span>
          <textarea
            className="schema-json-editor"
            rows={14}
            value={jsonText}
            onChange={(e) => onJsonTextChange(e.target.value)}
            spellCheck={false}
            aria-invalid={jsonInvalid}
          />
        </label>
      )}

      {editorTab === "summary" ? (
        <label className="field-label schema-editor-json-fallback">
          <span className="muted small">Raw JSON (edit here or use JSON tab)</span>
          <textarea
            className="schema-json-editor schema-json-editor--short"
            rows={6}
            value={jsonText}
            onChange={(e) => onJsonTextChange(e.target.value)}
            spellCheck={false}
          />
        </label>
      ) : null}

      <details className="schema-advanced-details">
        <summary className="schema-advanced-summary">Advanced rules (cross-field &amp; repeating tables)</summary>
        <div className="schema-advanced-body">
          <section className="schema-advanced-block" aria-label="Cross-field rule">
            <h3 className="schema-advanced-block-title">Cross-field rule</h3>
            <div className="schema-m3-form-grid">
              <label className="field-label">
                <span>Rule id</span>
                <input value={cfRuleId} onChange={(e) => setCfRuleId(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label">
                <span>Expression</span>
                <input value={cfExpression} onChange={(e) => setCfExpression(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label schema-m3-field-wide">
                <span>Error message</span>
                <input value={cfErrorMessage} onChange={(e) => setCfErrorMessage(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label">
                <span>Fields (comma-separated)</span>
                <input value={cfFieldsCsv} onChange={(e) => setCfFieldsCsv(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label schema-m3-field-wide">
                <span>Describe in plain language (optional LLM)</span>
                <textarea
                  className="schema-m3-nl-textarea"
                  rows={2}
                  value={cfAssistNl}
                  onChange={(e) => setCfAssistNl(e.target.value)}
                />
              </label>
            </div>
            <div className="schema-m3-llm-row">
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={busy || !projectId}
                onClick={() => {
                  const names = cfFieldsCsv
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  if (!names.length) {
                    onError("Add at least one field name before using LLM assist.");
                    return;
                  }
                  void (async () => {
                    try {
                      const out = await api.validation.suggestCrossFieldRule(projectId, {
                        natural_language: cfAssistNl.trim(),
                        allowed_field_names: names,
                      });
                      setCfRuleId(out.id);
                      setCfExpression(out.expression);
                      setCfErrorMessage(out.error_message);
                    } catch (e: unknown) {
                      onError(e instanceof Error ? e.message : String(e));
                    }
                  })();
                }}
              >
                Generate with LLM
              </button>
              <span className="muted tiny">Requires server LLM assist + Ollama.</span>
            </div>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => {
                try {
                  onJsonTextChange(
                    appendM3CrossFieldFromForm(jsonText, {
                      id: cfRuleId,
                      expression: cfExpression,
                      error_message: cfErrorMessage,
                      fieldsCsv: cfFieldsCsv,
                    }),
                  );
                } catch {
                  onError("Invalid JSON — fix syntax before appending.");
                }
              }}
            >
              Append to JSON
            </button>
          </section>

          <section className="schema-advanced-block" aria-label="Repeating group">
            <h3 className="schema-advanced-block-title">Repeating group</h3>
            <div className="schema-m3-form-grid">
              <label className="field-label">
                <span>Group key</span>
                <input value={rgGroupKey} onChange={(e) => setRgGroupKey(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label">
                <span>Section in PDF</span>
                <input value={rgSectionHint} onChange={(e) => setRgSectionHint(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label schema-m3-field-wide">
                <span>Layout</span>
                <select
                  className="schema-m3-select"
                  value={rgStructure}
                  onChange={(e) => setRgStructure(e.target.value as M3GroupStructure)}
                >
                  <option value="list">List (values on one line)</option>
                  <option value="table">Table (columns / pipes)</option>
                  <option value="sections">Sections (paragraphs)</option>
                </select>
              </label>
              <label className="field-label">
                <span>Row rule id</span>
                <input value={rgRuleId} onChange={(e) => setRgRuleId(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label schema-m3-field-wide">
                <span>Row expression</span>
                <input value={rgExpression} onChange={(e) => setRgExpression(e.target.value)} spellCheck={false} />
              </label>
              <label className="field-label schema-m3-field-wide">
                <span>Row error message</span>
                <input value={rgErrorMessage} onChange={(e) => setRgErrorMessage(e.target.value)} spellCheck={false} />
              </label>
            </div>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => {
                try {
                  onJsonTextChange(
                    appendM3RepeatingGroupFromForm(jsonText, {
                      groupKey: rgGroupKey,
                      sectionHint: rgSectionHint,
                      structureHint: rgStructure,
                      rowRuleId: rgRuleId,
                      rowExpression: rgExpression,
                      rowErrorMessage: rgErrorMessage,
                    }),
                  );
                } catch {
                  onError("Invalid JSON — fix syntax before appending.");
                }
              }}
            >
              Append to JSON
            </button>
          </section>
        </div>
      </details>

      <div className="schema-editor-actions row">
        <button type="submit" className="btn-primary-lg" disabled={busy || jsonInvalid}>
          Publish revision
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
