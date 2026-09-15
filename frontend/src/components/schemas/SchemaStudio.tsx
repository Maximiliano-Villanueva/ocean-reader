/**
 * Unified schema editor: wizard, workspace (outline + focus), simple cards, JSON, assistant, live test.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { ValidateDocumentResponse } from "../../api";
import { api } from "../../api";
import {
  addOpenEndedField,
  addStrictField,
  buildAgentValidationFeedback,
  getCrossFieldRules,
  getFieldsMap,
  getRepeatingGroups,
  parseSchemaJsonText,
  setCrossFieldRules,
  stringifySchemaBody,
  summarizePreviewForAgent,
  type SchemaJudgeFeedback,
} from "../../lib/schemaModel";
import {
  type SchemaEditorLayoutMode,
  type SchemaOutlineSelection,
  SCHEMA_UI,
} from "../../lib/schemaUiLabels";
import { appendM3RepeatingGroupFromForm, type M3GroupStructure } from "../../lib/schemaM3Snippets";
import SchemaAgentPanel from "./SchemaAgentPanel";
import SchemaDryRunPanel from "./SchemaDryRunPanel";
import SchemaFocusPanel from "./SchemaFocusPanel";
import SchemaOutlineNav from "./SchemaOutlineNav";
import SchemaSimpleCardsEditor from "./SchemaSimpleCardsEditor";
import SchemaWizard from "./SchemaWizard";

export type SchemaStudioProps = {
  projectId: string;
  jsonText: string;
  onJsonTextChange: (text: string) => void;
  schemaKey: string;
  onSchemaKeyChange?: (key: string) => void;
  disabled?: boolean;
  onDslStatusChange?: (ok: boolean | null, errors: string[]) => void;
  onError?: (message: string) => void;
  /** New schemas start in wizard; revisions start in workspace. */
  initialLayout?: SchemaEditorLayoutMode;
  /** Notifies parent when the user switches wizard / workspace / JSON / simple. */
  onLayoutChange?: (layout: SchemaEditorLayoutMode) => void;
};

export default function SchemaStudio({
  projectId,
  jsonText,
  onJsonTextChange,
  schemaKey,
  onSchemaKeyChange,
  disabled,
  onDslStatusChange,
  onError,
  initialLayout = "workspace",
  onLayoutChange,
}: SchemaStudioProps) {
  const [layout, setLayout] = useState<SchemaEditorLayoutMode>(initialLayout);

  const changeLayout = useCallback(
    (next: SchemaEditorLayoutMode) => {
      setLayout(next);
      onLayoutChange?.(next);
    },
    [onLayoutChange],
  );

  useEffect(() => {
    onLayoutChange?.(layout);
  }, [layout, onLayoutChange]);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [selection, setSelection] = useState<SchemaOutlineSelection>({ kind: "welcome" });
  const [dslOk, setDslOk] = useState<boolean | null>(null);
  const [dslErrors, setDslErrors] = useState<string[]>([]);
  const [dslBusy, setDslBusy] = useState(false);
  const [judgeFeedback, setJudgeFeedback] = useState<SchemaJudgeFeedback | null>(null);
  const [agentFeedback, setAgentFeedback] = useState(buildAgentValidationFeedback({ ok: true, errors: [] }));
  const validateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const body = parseSchemaJsonText(jsonText);
  const jsonInvalid = body === null;

  const runDslValidate = useCallback(
    async (parsed: Record<string, unknown>) => {
      if (!projectId) return;
      setDslBusy(true);
      try {
        const out = await api.validation.validateSchemaBody(projectId, parsed);
        setDslOk(out.ok);
        setDslErrors(out.errors);
        onDslStatusChange?.(out.ok, out.errors);
        setAgentFeedback((prev) =>
          buildAgentValidationFeedback(
            { ok: out.ok, errors: out.errors },
            prev.preview_status
              ? { status: prev.preview_status, summary: prev.preview_summary ?? "" }
              : null,
            judgeFeedback,
          ),
        );
        if (out.normalized_body && JSON.stringify(out.normalized_body) !== JSON.stringify(parsed)) {
          onJsonTextChange(stringifySchemaBody(out.normalized_body));
        }
      } catch {
        setDslOk(false);
        setDslErrors(["Could not reach validation API."]);
      } finally {
        setDslBusy(false);
      }
    },
    [projectId, onJsonTextChange, onDslStatusChange, judgeFeedback],
  );

  useEffect(() => {
    if (!body || !projectId) {
      setDslOk(null);
      setDslErrors([]);
      onDslStatusChange?.(null, []);
      return;
    }
    if (validateTimer.current) clearTimeout(validateTimer.current);
    validateTimer.current = setTimeout(() => {
      void runDslValidate(body);
    }, 600);
    return () => {
      if (validateTimer.current) clearTimeout(validateTimer.current);
    };
  }, [jsonText, projectId, body, runDslValidate, onDslStatusChange]);

  function onBodyChange(next: Record<string, unknown>) {
    onJsonTextChange(stringifySchemaBody(next));
  }

  function patch(fn: (b: Record<string, unknown>) => Record<string, unknown>) {
    if (!body) return;
    onBodyChange(fn(body));
  }

  function onAddStrict() {
    if (!body) return;
    const next = addStrictField(body, "");
    onBodyChange(next);
    const names = Object.keys(getFieldsMap(next));
    const added = names[names.length - 1];
    if (added) setSelection({ kind: "strict", field: added });
  }

  function onAddOpenEnded() {
    if (!body) return;
    const oe = { ...(body.open_ended as Record<string, unknown> | undefined) };
    const key = `insight_${Object.keys(oe).length + 1}`;
    onBodyChange(addOpenEndedField(body, key));
    setSelection({ kind: "open_ended", field: key });
  }

  function onAddCross() {
    if (!body) return;
    const rules = getCrossFieldRules(body);
    patch((b) =>
      setCrossFieldRules(b, [
        ...rules,
        { id: `rule_${rules.length + 1}`, expression: "", error_message: "Rule failed", fields: [] },
      ]),
    );
    setSelection({ kind: "cross", index: rules.length });
  }

  function onAddGroup() {
    if (!body) return;
    const groups = getRepeatingGroups(body);
    const text = appendM3RepeatingGroupFromForm(stringifySchemaBody(body), {
      groupKey: `group_${Object.keys(groups).length + 1}`,
      sectionHint: "Section title",
      structureHint: "list" as M3GroupStructure,
      rowRuleId: "within_spec",
      rowExpression: "true",
      rowErrorMessage: "Row failed",
    });
    const parsed = JSON.parse(text) as Record<string, unknown>;
    onBodyChange(parsed);
    const keys = Object.keys(getRepeatingGroups(parsed));
    const added = keys[keys.length - 1];
    if (added) setSelection({ kind: "group", key: added });
  }

  async function onPreviewComplete(response: ValidateDocumentResponse) {
    const summary = summarizePreviewForAgent(
      response.status,
      response.resolved_values ?? undefined,
      response.results.map((e) => ({ field: e.field, rule: e.rule })),
      response.ambiguous_fields,
      response.open_ended_results ?? [],
    );
    let judge: SchemaJudgeFeedback | null = null;
    try {
      const parsed = parseSchemaJsonText(jsonText);
      if (parsed) {
        judge = await api.validation.schemaJudgeAnalyze(projectId, {
          schema_body: parsed,
          dsl_errors: dslErrors,
          validation: response,
        });
        setJudgeFeedback(judge);
      }
    } catch {
      /* optional */
    }
    setAgentFeedback(
      buildAgentValidationFeedback(
        { ok: dslOk !== false, errors: dslErrors },
        { status: response.status, summary },
        judge,
      ),
    );
  }

  if (layout === "wizard" && body && onSchemaKeyChange) {
    return (
      <div className="schema-studio schema-studio--wizard">
        <SchemaWizard
          projectId={projectId}
          schemaKey={schemaKey}
          onSchemaKeyChange={onSchemaKeyChange}
          body={body}
          onBodyChange={onBodyChange}
          jsonText={jsonText}
          jsonInvalid={jsonInvalid}
          disabled={disabled}
          onComplete={() => changeLayout("workspace")}
        />
      </div>
    );
  }

  const shellClass = [
    "schema-studio",
    assistantOpen ? "schema-studio--assistant-open" : "schema-studio--no-assistant",
    layout === "simple" ? "schema-studio--simple" : "",
    layout === "workspace" ? "schema-studio--workspace" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClass}>
      <header className="schema-studio-topbar">
        <div className="schema-layout-toggle" role="tablist" aria-label="Editor layout">
          {(
            [
              ["workspace", "Workspace"],
              ["simple", "Simple"],
              ["json", "JSON"],
              ["wizard", "Wizard"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={layout === id}
              className={`schema-layout-toggle-btn ${layout === id ? "schema-layout-toggle-btn--active" : ""}`}
              onClick={() => changeLayout(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="schema-studio-topbar-spacer" />
        <button
          type="button"
          className="schema-studio-assistant-toggle"
          onClick={() => setAssistantOpen((o) => !o)}
          aria-pressed={assistantOpen}
        >
          {assistantOpen ? "Hide assistant" : SCHEMA_UI.assistantTitle}
        </button>
        <div className="schema-studio-dsl-status" aria-live="polite">
          {jsonInvalid ? (
            <span className="schema-dsl-badge schema-dsl-badge--error">Invalid JSON</span>
          ) : dslBusy ? (
            <span className="schema-dsl-badge schema-dsl-badge--pending">Checking…</span>
          ) : dslOk === true ? (
            <span className="schema-dsl-badge schema-dsl-badge--ok">Valid</span>
          ) : dslOk === false ? (
            <span className="schema-dsl-badge schema-dsl-badge--error">Needs fixes</span>
          ) : null}
        </div>
      </header>

      {!jsonInvalid && dslErrors.length > 0 ? (
        <div className="schema-dsl-errors" role="alert">
          <strong>Fix before publishing</strong>
          <ul>
            {dslErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div
        className={[
          "schema-studio-body",
          assistantOpen ? "schema-studio-body--assistant-open" : "schema-studio-body--no-assistant",
          layout === "workspace" ? "schema-studio-body--workspace" : "",
          layout === "simple" ? "schema-studio-body--simple" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {assistantOpen ? (
          <aside className="schema-studio-assistant-pane" aria-label="Schema assistant">
            <header className="schema-assistant-pane-head">
              <h3>{SCHEMA_UI.assistantTitle}</h3>
              <p className="muted small">{SCHEMA_UI.assistantLead}</p>
            </header>
            <SchemaAgentPanel
              projectId={projectId}
              schemaBody={body ?? {}}
              validationFeedback={agentFeedback}
              disabled={disabled || jsonInvalid}
              onSchemaBodyChange={(b) => onJsonTextChange(stringifySchemaBody(b))}
              layout="studio"
            />
          </aside>
        ) : null}

        {layout === "workspace" && body ? (
          <>
            <aside className="schema-studio-outline-pane">
              <SchemaOutlineNav
                body={body}
                selection={selection}
                onSelect={setSelection}
                onAddStrict={onAddStrict}
                onAddOpenEnded={onAddOpenEnded}
                onAddCross={onAddCross}
                onAddGroup={onAddGroup}
                disabled={disabled}
              />
            </aside>
            <main className="schema-studio-center-pane">
              <div className="schema-studio-center-scroll">
                <SchemaFocusPanel
                projectId={projectId}
                body={body}
                selection={selection}
                disabled={disabled}
                onBodyChange={onBodyChange}
                onError={onError}
                onAddStrict={onAddStrict}
              />
              </div>
            </main>
          </>
        ) : null}

        {layout === "simple" && body ? (
          <main className="schema-studio-center-pane schema-studio-center-pane--simple">
            <div className="schema-studio-center-scroll">
              <SchemaSimpleCardsEditor
              projectId={projectId}
              body={body}
              disabled={disabled}
              onBodyChange={onBodyChange}
              onError={onError}
            />
            </div>
          </main>
        ) : null}

        {layout === "json" ? (
          <main className="schema-studio-center-pane">
            <label className="field-label">
              <span className="schema-studio-topbar-label">Definition JSON</span>
              <textarea
                className="schema-json-editor"
                value={jsonText}
                onChange={(e) => onJsonTextChange(e.target.value)}
                spellCheck={false}
                disabled={disabled}
              />
            </label>
          </main>
        ) : null}

        {layout === "wizard" && onSchemaKeyChange && body ? (
          <main className="schema-studio-center-pane schema-studio-center-pane--wizard-inline">
            <SchemaWizard
              projectId={projectId}
              schemaKey={schemaKey}
              onSchemaKeyChange={onSchemaKeyChange}
              body={body}
              onBodyChange={onBodyChange}
              jsonText={jsonText}
              jsonInvalid={jsonInvalid}
              disabled={disabled}
              onComplete={() => changeLayout("workspace")}
            />
          </main>
        ) : null}

        <aside className="schema-studio-rail-pane" aria-label="Live test">
          <section className="schema-studio-rail-section">
            <h3 className="schema-studio-rail-heading">{SCHEMA_UI.testPdf}</h3>
            <p className="schema-studio-rail-lead muted small">
              Upload a sample document and see extracted values without saving a run.
            </p>
            <SchemaDryRunPanel
              projectId={projectId}
              jsonText={jsonText}
              jsonInvalid={jsonInvalid}
              disabled={disabled}
              variant="rail"
              onPreviewComplete={(r) => void onPreviewComplete(r)}
            />
          </section>
          {judgeFeedback?.summary ? (
            <section className="schema-studio-rail-section schema-judge-feedback">
              <h3 className="schema-judge-feedback-title">Judge feedback</h3>
              <p>{judgeFeedback.summary}</p>
              {judgeFeedback.recommendations.length > 0 ? (
                <ul className="schema-judge-feedback-list">
                  {judgeFeedback.recommendations.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
