/**
 * Schema library — one schema key per block; each version is a full-width row.
 */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import SchemaVersionTable from "../components/schemas/SchemaVersionTable";
import { formatSchemaKey } from "../lib/displayLabels";
import {
  api,
  type ValidationSchemaGroupOut,
  type ValidationSchemaVersionDetailOut,
} from "../api";

export default function ProjectSchemasPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const [groups, setGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [detailById, setDetailById] = useState<Record<string, ValidationSchemaVersionDetailOut>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState<string | null>(null);

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

  function openEditor(schemaKey: string, fromVersionId?: string) {
    const base = `/projects/${projectId}/schemas/${encodeURIComponent(schemaKey)}/edit`;
    navigate(fromVersionId ? `${base}?from=${encodeURIComponent(fromVersionId)}` : base);
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
      <header className="schemas-hero schemas-hero--compact">
        <div className="schemas-hero-text">
          <h1 className="hero-title">Checklists</h1>
          <p className="hero-sub muted">
            Each checklist groups immutable versions of your acceptance rules. Publish a new version when
            specifications change — history is always kept for audits.
          </p>
        </div>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="schemas-toolbar">
        <Link
          to={`/projects/${projectId}/schemas/new`}
          className="btn-primary-lg"
          style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
        >
          New checklist
        </Link>
        <p className="schemas-toolbar-hint">
          Opens the guided wizard. Switch to workspace or simple mode anytime while editing.
        </p>
      </div>

      <section className="schemas-main schemas-main--list" aria-label="Schema keys">
        {groups.length === 0 ? (
          <div className="schemas-empty">
            <p className="muted">No checklists yet.</p>
            <p className="muted small" style={{ marginTop: "0.5rem" }}>
              Create your first checklist with the wizard — document type, fields, PDF settings, then test.
            </p>
          </div>
        ) : (
          <div className="schemas-group-list">
            {groups.map((g) => {
              const sorted = [...g.versions].sort((a, b) =>
                (b.created_at ?? "").localeCompare(a.created_at ?? ""),
              );
              const active = g.versions.find((v) => v.status === "active") ?? sorted[0];
              return (
                <section key={g.schema_key} className="schema-group-block" aria-label={`Checklist ${g.schema_key}`}>
                  <header className="schema-group-block-head">
                    <div className="schema-group-block-title-wrap">
                      <h2 className="schema-group-block-title">{formatSchemaKey(g.schema_key)}</h2>
                      <p className="schema-group-block-meta muted small">
                        <code className="schema-key-technical">{g.schema_key}</code>
                        {" · "}
                        {g.versions.length} version{g.versions.length === 1 ? "" : "s"}
                        {active ? (
                          <>
                            {" "}
                            · active <strong>v{active.version_label}</strong>
                          </>
                        ) : null}
                      </p>
                    </div>
                    <div className="schema-group-block-actions">
                      <Link
                        to={`/projects/${projectId}/schemas/${encodeURIComponent(g.schema_key)}/edit`}
                        className="btn-primary btn-sm"
                        style={{ textDecoration: "none" }}
                      >
                        Edit checklist
                      </Link>
                    </div>
                  </header>
                  <div className="schema-group-versions">
                    <SchemaVersionTable
                      schemaKey={g.schema_key}
                      versions={sorted}
                      expandedId={expandedId}
                      detailById={detailById}
                      detailLoading={detailLoading}
                      busy={busy}
                      layout="rows"
                      onToggleDefinition={toggleDefinition}
                      onForkRevision={(v) => openEditor(g.schema_key, v.id)}
                      onDelete={removeVersion}
                    />
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
