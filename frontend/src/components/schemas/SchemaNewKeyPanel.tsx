/**
 * Form to create a brand-new schema key with a first revision.
 */

import { type FormEvent } from "react";

import {
  appendM3RepeatingGroupSnippet,
  appendM3WineCrossFieldRule,
} from "../../lib/schemaM3Snippets";

export type SchemaNewKeyPanelProps = {
  newKey: string;
  newKeyBody: string;
  busy: boolean;
  wineTemplate: string;
  onKeyChange: (key: string) => void;
  onBodyChange: (body: string) => void;
  onSubmit: (e: FormEvent) => void;
  onClose: () => void;
  onError: (message: string) => void;
};

export default function SchemaNewKeyPanel({
  newKey,
  newKeyBody,
  busy,
  wineTemplate,
  onKeyChange,
  onBodyChange,
  onSubmit,
  onClose,
  onError,
}: SchemaNewKeyPanelProps) {
  return (
    <form className="schema-editor-panel" onSubmit={onSubmit}>
      <header className="schema-editor-panel-header">
        <h2 className="schema-editor-panel-title">New schema key</h2>
        <p className="muted small">First revision for a new document type. Use a short snake_case key.</p>
      </header>

      <label className="field-label">
        <span>Schema key</span>
        <input
          value={newKey}
          onChange={(e) => onKeyChange(e.target.value)}
          placeholder="customer_coa"
          spellCheck={false}
          autoFocus
        />
      </label>

      <label className="field-label">
        <span>Definition JSON</span>
        <textarea
          className="schema-json-editor"
          rows={12}
          value={newKeyBody}
          onChange={(e) => onBodyChange(e.target.value)}
          spellCheck={false}
        />
      </label>

      <p className="schema-quick-insert muted small">
        Quick insert:{" "}
        <button type="button" className="btn-inline link-button" onClick={() => onBodyChange(wineTemplate)}>
          Wine template
        </button>
        {" · "}
        <button
          type="button"
          className="btn-inline link-button"
          onClick={() => {
            try {
              onBodyChange(appendM3WineCrossFieldRule(newKeyBody));
            } catch {
              onError("Invalid JSON.");
            }
          }}
        >
          + cross-field example
        </button>
        {" · "}
        <button
          type="button"
          className="btn-inline link-button"
          onClick={() => {
            try {
              onBodyChange(appendM3RepeatingGroupSnippet(newKeyBody));
            } catch {
              onError("Invalid JSON.");
            }
          }}
        >
          + repeating group example
        </button>
      </p>

      <div className="schema-editor-actions row">
        <button type="submit" className="btn-primary-lg" disabled={busy}>
          Create schema
        </button>
        <button type="button" className="btn-secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}
