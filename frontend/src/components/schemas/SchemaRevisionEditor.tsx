/**
 * Schema authoring: command bar + checklist studio with publish gate on DSL validity.
 */

import { type FormEvent, useState } from "react";

import { formatSchemaKey } from "../../lib/displayLabels";
import type { SchemaEditorLayoutMode } from "../../lib/schemaUiLabels";
import SchemaStudio from "./SchemaStudio";

export type SchemaComposerMode = "create" | "revision";

export type SchemaRevisionEditorProps = {
  mode: SchemaComposerMode;
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
  mode,
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
  const isCreate = mode === "create";
  const [editorLayout, setEditorLayout] = useState<SchemaEditorLayoutMode>(isCreate ? "wizard" : "workspace");
  const [dslOk, setDslOk] = useState<boolean | null>(null);
  const hideCommandBarKey = isCreate && editorLayout === "wizard";
  let jsonInvalid = false;
  try {
    JSON.parse(jsonText);
  } catch {
    jsonInvalid = true;
  }
  const canPublish = !busy && !jsonInvalid && dslOk !== false && Boolean(schemaKey.trim());
  const displayName = schemaKey.trim() ? formatSchemaKey(schemaKey) : null;

  return (
    <form className="schema-composer" onSubmit={onPublish}>
      <header className="schema-command-bar">
        <button type="button" className="schema-command-bar-back" onClick={onCancel}>
          ← Back to checklists
        </button>
        <div className="schema-command-bar-title-wrap">
          <h2 className="schema-command-bar-title">{isCreate ? "New checklist" : "New version"}</h2>
          {displayName ? <p className="schema-command-bar-display muted small">{displayName}</p> : null}
        </div>
        {hideCommandBarKey ? (
          <p className="schema-command-bar-key-wizard-note muted small">
            Set the checklist ID in step 1 of the wizard below.
          </p>
        ) : (
          <label className="schema-command-bar-key field-label">
            <span className="schema-command-bar-key-label">Checklist ID</span>
            <input
              value={schemaKey}
              onChange={(e) => onSchemaKeyChange(e.target.value)}
              placeholder="e.g. supplier_coa"
              spellCheck={false}
              autoFocus={isCreate && editorLayout !== "wizard"}
              aria-label="Checklist ID"
            />
            <span className="schema-command-bar-key-hint muted small">
              Internal key — shown to users as a friendly name.
            </span>
          </label>
        )}
        <div className="schema-command-bar-actions">
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn-primary-lg" disabled={!canPublish}>
            {busy ? "Publishing…" : isCreate ? "Create checklist" : "Publish version"}
          </button>
        </div>
        <p className="schema-command-bar-hint">
          {isCreate
            ? "Use the wizard, workspace, or JSON. Rules must validate before you can publish."
            : `Based on ${displayName ?? (schemaKey || "…")} — publishing creates the next version when rules are valid.`}
          {dslOk === false ? " · Fix validation errors before publishing." : null}
        </p>
      </header>

      <section className="schema-composer-primary" aria-label="Checklist studio">
        <SchemaStudio
          projectId={projectId}
          schemaKey={schemaKey}
          onSchemaKeyChange={onSchemaKeyChange}
          jsonText={jsonText}
          onJsonTextChange={onJsonTextChange}
          disabled={busy}
          initialLayout={isCreate ? "wizard" : "workspace"}
          onLayoutChange={setEditorLayout}
          onDslStatusChange={(ok) => setDslOk(ok)}
          onError={onError}
        />
      </section>
    </form>
  );
}
