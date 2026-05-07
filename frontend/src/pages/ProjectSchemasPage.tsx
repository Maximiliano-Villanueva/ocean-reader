import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  api,
  type ValidationSchemaGroupOut,
  type ValidationSchemaVersionDetailOut,
  type ValidationSchemaVersionSummary,
} from "../api";

const DEFAULT_WINE_SCHEMA_KEY = "wine_quality";

/** Mirrors server default — lets users start a brand-new key without guessing shape. */
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

export default function ProjectSchemasPage() {
  const { projectId = "" } = useParams();
  const [groups, setGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** Row id → loaded definition */
  const [detailById, setDetailById] = useState<Record<string, ValidationSchemaVersionDetailOut>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  /** Fork-edit: publish as next server-assigned revision */
  const [revisionDraft, setRevisionDraft] = useState<{ schema_key: string; jsonText: string } | null>(null);
  /** Optional new schema key + body for first revision */
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

  function useAsRevisionBase(v: ValidationSchemaVersionSummary, schemaKey: string) {
    const cached = detailById[v.id];
    const jsonText = cached
      ? JSON.stringify(cached.body, null, 2)
      : "// Click ‘Show definition’ first to load JSON, or paste below.";
    setRevisionDraft({ schema_key: schemaKey, jsonText });
    setExpandedId(v.id);
    if (!cached && projectId) {
      void (async () => {
        setDetailLoading(v.id);
        try {
          const d = await api.validation.getSchemaVersion(projectId, v.id);
          setDetailById((prev) => ({ ...prev, [v.id]: d }));
          setRevisionDraft({ schema_key: schemaKey, jsonText: JSON.stringify(d.body, null, 2) });
        } catch (err: unknown) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          setDetailLoading(null);
        }
      })();
    }
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

  return (
    <div className="page project-route-page schemas-page">
      <header className="hero-block">
        <h1 className="hero-title">Schemas &amp; revisions</h1>
        <p className="hero-sub muted">
          A <strong>schema key</strong> (e.g. <code>wine_quality</code>) names one rule bundle. Each save creates an
          immutable <strong>revision</strong>; the server assigns the next label (<code>1.0</code> → <code>1.1</code>
          …). You do not invent version strings unless you use Advanced mode.
        </p>
        <p className="muted small">
          <Link to={`/projects/${projectId}/validation`}>Validation history</Link>
          {" · "}
          <Link to={`/projects/${projectId}/validation/run`}>Run validation</Link>
        </p>
      </header>

      <section className="panel-block schema-explainer">
        <h2 className="section-heading">Does the default include rules?</h2>
        <p className="muted">
          Yes. The built-in wine-quality definition includes three numeric fields (<code>ph</code>, <code>alcohol</code>,{" "}
          <code>quality</code>) with min/max and aliases, plus <code>rules</code>:{" "}
          <code>required</code>, <code>range_validation</code>, <code>type_check</code>. Use <strong>Show definition</strong>{" "}
          on any row to see the stored JSON.
        </p>
      </section>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <section className="panel-block">
        <h2 className="section-heading">Install default bundle</h2>
        <p className="muted small">
          Creates (or adds the next revision of) <code>{DEFAULT_WINE_SCHEMA_KEY}</code> using the server&apos;s
          wine-quality JSON. Safe to click multiple times — each click adds revision <code>1.1</code>,{" "}
          <code>1.2</code>, …
        </p>
        <button type="button" className="btn-secondary" disabled={busy || !projectId} onClick={() => void installDefault()}>
          {busy ? "Working…" : `Install / bump ${DEFAULT_WINE_SCHEMA_KEY}`}
        </button>
      </section>

      <section className="panel-block">
        <h2 className="section-heading">Edit → new revision</h2>
        <p className="muted small">
          Schemas are immutable: &quot;editing&quot; means editing JSON here and publishing — the previous revision stays
          in history (archived when a new one becomes active).
        </p>
        {revisionDraft ? (
          <form className="schema-revision-form" onSubmit={publishRevision}>
            <label className="field-label">
              <span>Schema key (unchanged for same bundle)</span>
              <input
                value={revisionDraft.schema_key}
                onChange={(e) => setRevisionDraft((d) => (d ? { ...d, schema_key: e.target.value } : null))}
                spellCheck={false}
              />
            </label>
            <label className="field-label">
              <span>Definition JSON</span>
              <textarea
                className="schema-json-editor"
                rows={18}
                value={revisionDraft.jsonText}
                onChange={(e) => setRevisionDraft((d) => (d ? { ...d, jsonText: e.target.value } : null))}
                spellCheck={false}
              />
            </label>
            <div className="row">
              <button type="submit" className="btn-primary-lg" disabled={busy}>
                Publish new revision (auto label)
              </button>
              <button type="button" className="btn-secondary" onClick={() => setRevisionDraft(null)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <p className="muted small">Choose <strong>Use as base for new revision</strong> on a version below.</p>
        )}
      </section>

      <section className="panel-block">
        <h2 className="section-heading">New schema key (first revision)</h2>
        <p className="muted small">
          Use a new <code>schema_key</code> when the document type is not wine. Paste a full JSON body; template inserts
          the wine shape as a starting point.
        </p>
        <form className="schema-new-form" onSubmit={publishNewSchemaFirstRevision}>
          <label className="field-label">
            <span>Schema key</span>
            <input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="my_customer_form" spellCheck={false} />
          </label>
          <label className="field-label">
            <span>Definition JSON</span>
            <textarea className="schema-json-editor" rows={14} value={newKeyBody} onChange={(e) => setNewKeyBody(e.target.value)} spellCheck={false} />
          </label>
          <div className="row">
            <button type="button" className="btn-secondary" onClick={() => setNewKeyBody(WINE_QUALITY_TEMPLATE)}>
              Insert wine template
            </button>
            <button type="submit" className="btn-primary-lg" disabled={busy}>
              Publish first revision (auto label)
            </button>
          </div>
        </form>
      </section>

      <section className="panel-block">
        <h2 className="section-heading">All schema keys</h2>
        {groups.length === 0 ? (
          <p className="muted">No schemas yet — install the default or create a new key above.</p>
        ) : (
          <ul className="list schema-card-list">
            {groups.map((g) => (
              <li key={g.schema_key} className="schema-card">
                <h3 className="schema-card-title">
                  <code>{g.schema_key}</code>
                </h3>
                <ul className="list schema-version-sublist">
                  {g.versions.map((v) => (
                    <li key={v.id} className="schema-version-block">
                      <div className="schema-version-row">
                        <span>
                          <strong>{v.version_label}</strong>{" "}
                          <span className="muted">
                            ({v.status}) {v.created_at ? `· ${v.created_at}` : ""}
                          </span>
                        </span>
                        <span className="schema-version-actions">
                          <button type="button" className="btn-inline" disabled={busy} onClick={() => void toggleDefinition(v.id)}>
                            {expandedId === v.id ? "Hide" : "Show"} definition
                          </button>
                          <button
                            type="button"
                            className="btn-inline"
                            disabled={busy}
                            onClick={() => useAsRevisionBase(v, g.schema_key)}
                          >
                            Use as base for new revision
                          </button>
                          <button
                            type="button"
                            className="danger btn-inline"
                            disabled={busy}
                            onClick={() => void removeVersion(v.id, `${g.schema_key}@${v.version_label}`)}
                          >
                            Delete
                          </button>
                        </span>
                      </div>
                      {detailLoading === v.id ? <p className="muted small">Loading…</p> : null}
                      {expandedId === v.id && detailById[v.id] ? (
                        <pre className="schema-json-view">{JSON.stringify(detailById[v.id].body, null, 2)}</pre>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
