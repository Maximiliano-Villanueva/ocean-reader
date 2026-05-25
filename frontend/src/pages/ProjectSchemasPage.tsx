/**
 * Schema keys and immutable revisions — browse, view rules, fork new revisions.
 */

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import SchemaNewKeyPanel from "../components/schemas/SchemaNewKeyPanel";
import SchemaRevisionEditor from "../components/schemas/SchemaRevisionEditor";
import SchemaVersionTable from "../components/schemas/SchemaVersionTable";
import {
  api,
  type ValidationSchemaGroupOut,
  type ValidationSchemaVersionDetailOut,
  type ValidationSchemaVersionSummary,
} from "../api";

const DEFAULT_WINE_SCHEMA_KEY = "wine_quality";

const WINE_QUALITY_TEMPLATE = `{
  "fields": {
    "ph": {
      "type": "number",
      "required": true,
      "min": 2.5,
      "max": 4.5,
      "aliases": ["pH", "Measured pH"]
    },
    "alcohol": {
      "type": "number",
      "required": true,
      "min": 8.0,
      "max": 15.0,
      "aliases": ["Alcohol", "Alcohol %"]
    },
    "quality": {
      "type": "number",
      "required": true,
      "min": 0,
      "max": 10,
      "aliases": ["Quality", "Quality score"]
    }
  },
  "rules": ["required", "range_validation", "type_check"]
}`;

type EditorMode = "none" | "revision" | "new-key";

export default function ProjectSchemasPage() {
  const { projectId = "" } = useParams();
  const [groups, setGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [detailById, setDetailById] = useState<Record<string, ValidationSchemaVersionDetailOut>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [revisionDraft, setRevisionDraft] = useState<{ schema_key: string; jsonText: string } | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>("none");
  const [newKey, setNewKey] = useState("");
  const [newKeyBody, setNewKeyBody] = useState(WINE_QUALITY_TEMPLATE);

  const load = useCallback(async () => {
    if (!projectId) return;
    setError(null);
    setGroups(await api.validation.listSchemas(projectId));
  }, [projectId]);

  useEffect(() => {
    load().catch((e: unknown) => {
      setError(e instanceof Error ? e.message : String(e));
    });
  }, [load]);

  async function installDefault() {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      await api.validation.createSchemaVersion(projectId, { schema_key: DEFAULT_WINE_SCHEMA_KEY });
      setRevisionDraft(null);
      setEditorMode("none");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleDefinition(rowId: string) {
    if (expandedId === rowId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(rowId);
    if (detailById[rowId]) return;
    if (!projectId) return;
    setDetailLoading(rowId);
    setError(null);
    try {
      const d = await api.validation.getSchemaVersion(projectId, rowId);
      setDetailById((prev) => ({ ...prev, [rowId]: d }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setExpandedId(null);
    } finally {
      setDetailLoading(null);
    }
  }

  function startRevisionFromVersion(v: ValidationSchemaVersionSummary, schemaKey: string) {
    setEditorMode("revision");
    setExpandedId(v.id);
    const cached = detailById[v.id];
    if (cached) {
      setRevisionDraft({ schema_key: schemaKey, jsonText: JSON.stringify(cached.body, null, 2) });
      return;
    }
    setRevisionDraft({
      schema_key: schemaKey,
      jsonText: "// Loading definition…",
    });
    if (!projectId) return;
    void (async () => {
      setDetailLoading(v.id);
      try {
        const d = await api.validation.getSchemaVersion(projectId, v.id);
        setDetailById((prev) => ({ ...prev, [v.id]: d }));
        setRevisionDraft({ schema_key: schemaKey, jsonText: JSON.stringify(d.body, null, 2) });
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
        setRevisionDraft(null);
        setEditorMode("none");
      } finally {
        setDetailLoading(null);
      }
    })();
  }

  async function publishRevision(e: FormEvent) {
    e.preventDefault();
    if (!projectId || !revisionDraft) return;
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(revisionDraft.jsonText) as Record<string, unknown>;
    } catch {
      setError("Invalid JSON — fix the editor before publishing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.validation.createSchemaVersion(projectId, {
        schema_key: revisionDraft.schema_key.trim(),
        body,
      });
      setRevisionDraft(null);
      setEditorMode("none");
      setDetailById({});
      setExpandedId(null);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function publishNewSchemaFirstRevision(e: FormEvent) {
    e.preventDefault();
    if (!projectId) return;
    const sk = newKey.trim();
    if (!sk) {
      setError("Schema key is required.");
      return;
    }
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(newKeyBody) as Record<string, unknown>;
    } catch {
      setError("Invalid JSON for new schema.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.validation.createSchemaVersion(projectId, { schema_key: sk, body });
      setNewKey("");
      setNewKeyBody(WINE_QUALITY_TEMPLATE);
      setEditorMode("none");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeVersion(schemaRowId: string, label: string) {
    if (!projectId) return;
    if (!confirm(`Delete revision ${label}? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.validation.deleteSchemaVersion(projectId, schemaRowId);
      setDetailById((prev) => {
        const next = { ...prev };
        delete next[schemaRowId];
        return next;
      });
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const asideOpen = editorMode !== "none";

  return (
    <div className={`page project-route-page schemas-page ${asideOpen ? "schemas-page--editing" : ""}`.trim()}>
      <header className="schemas-hero hero-block">
        <div className="schemas-hero-text">
          <h1 className="hero-title">Schemas &amp; revisions</h1>
          <p className="hero-sub muted">
            Each <strong>schema key</strong> is one rule bundle. Saving always creates a new{" "}
            <strong>revision</strong> (1.0, 1.1, …). Previous revisions stay in history.
          </p>
        </div>
        <nav className="schemas-hero-links muted small">
          <Link to={`/projects/${projectId}/validation/run`}>Run validation</Link>
          <span aria-hidden="true"> · </span>
          <Link to={`/projects/${projectId}/validation`}>History</Link>
        </nav>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="schemas-toolbar panel-block">
        <div className="schemas-toolbar-actions row">
          <button
            type="button"
            className="btn-secondary"
            disabled={busy || !projectId}
            onClick={() => void installDefault()}
          >
            {busy ? "Working…" : `Install wine template (${DEFAULT_WINE_SCHEMA_KEY})`}
          </button>
          <button
            type="button"
            className="btn-primary-lg"
            disabled={busy}
            onClick={() => {
              setRevisionDraft(null);
              setEditorMode("new-key");
              setError(null);
            }}
          >
            + New schema key
          </button>
        </div>
        <p className="schemas-toolbar-hint muted small">
          To change rules: open a version → <strong>New revision from this</strong>, edit, then publish. The active
          revision is what validation uses by default.
        </p>
      </div>

      <div className="schemas-layout">
        <section className="schemas-main" aria-label="Schema keys">
          {groups.length === 0 ? (
            <div className="schemas-empty panel-block">
              <p className="muted">No schemas yet.</p>
              <p className="muted small">
                Install the wine template or create a new schema key to get started.
              </p>
            </div>
          ) : (
            <ul className="list schemas-key-list">
              {groups.map((g) => (
                <li key={g.schema_key} className="schema-key-card panel-block">
                  <div className="schema-key-card-header">
                    <h2 className="schema-key-card-title">
                      <code>{g.schema_key}</code>
                    </h2>
                    <span className="muted small">
                      {g.versions.length} revision{g.versions.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <SchemaVersionTable
                    schemaKey={g.schema_key}
                    versions={g.versions}
                    expandedId={expandedId}
                    detailById={detailById}
                    detailLoading={detailLoading}
                    busy={busy}
                    onToggleDefinition={toggleDefinition}
                    onForkRevision={(v) => startRevisionFromVersion(v, g.schema_key)}
                    onDelete={removeVersion}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        {asideOpen ? (
          <aside className="schemas-aside" aria-label="Schema editor">
            {editorMode === "revision" && revisionDraft ? (
              <SchemaRevisionEditor
                projectId={projectId}
                schemaKey={revisionDraft.schema_key}
                jsonText={revisionDraft.jsonText}
                busy={busy}
                onSchemaKeyChange={(key) => setRevisionDraft((d) => (d ? { ...d, schema_key: key } : null))}
                onJsonTextChange={(text) => setRevisionDraft((d) => (d ? { ...d, jsonText: text } : null))}
                onPublish={publishRevision}
                onCancel={() => {
                  setRevisionDraft(null);
                  setEditorMode("none");
                }}
                onError={setError}
              />
            ) : null}
            {editorMode === "new-key" ? (
              <SchemaNewKeyPanel
                newKey={newKey}
                newKeyBody={newKeyBody}
                busy={busy}
                wineTemplate={WINE_QUALITY_TEMPLATE}
                onKeyChange={setNewKey}
                onBodyChange={setNewKeyBody}
                onSubmit={publishNewSchemaFirstRevision}
                onClose={() => setEditorMode("none")}
                onError={setError}
              />
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
