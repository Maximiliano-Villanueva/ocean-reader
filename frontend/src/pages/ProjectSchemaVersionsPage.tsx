import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type ValidationSchemaGroupOut, type ValidationSchemaVersionSummary } from "../api";

const PAGE_SIZE = 25;

type FlatRow = ValidationSchemaVersionSummary & { schema_key: string };

export default function ProjectSchemaVersionsPage() {
  const { projectId = "" } = useParams();
  const [groups, setGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);

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

  const flat = useMemo(() => {
    const rows: FlatRow[] = [];
    for (const g of groups) {
      for (const v of g.versions) {
        rows.push({ ...v, schema_key: g.schema_key });
      }
    }
    rows.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    return rows;
  }, [groups]);

  const totalPages = Math.max(1, Math.ceil(flat.length / PAGE_SIZE));
  const slice = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return flat.slice(start, start + PAGE_SIZE);
  }, [flat, page]);

  useEffect(() => {
    setPage(1);
  }, [groups]);

  async function removeRow(row: FlatRow) {
    if (!projectId) return;
    if (!confirm(`Delete ${row.schema_key} @ ${row.version_label}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.validation.deleteSchemaVersion(projectId, row.id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page project-route-page schema-versions-page">
      <header className="hero-block">
        <h1 className="hero-title">Schema versions</h1>
        <p className="hero-sub muted">Flat list of every immutable version (newest first). Same data as the Schemas page.</p>
        <p className="muted small">
          <Link to={`/projects/${projectId}/schemas`}>Grouped by schema</Link>
          {" · "}
          <Link to={`/projects/${projectId}/validation/run`}>Run validation</Link>
        </p>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {flat.length === 0 ? (
        <p className="muted">No versions yet.</p>
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Schema key</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {slice.map((row) => (
                  <tr key={`${row.schema_key}-${row.id}`}>
                    <td>
                      <code>{row.schema_key}</code>
                    </td>
                    <td>{row.version_label}</td>
                    <td>{row.status}</td>
                    <td className="muted small">{row.created_at ?? "—"}</td>
                    <td>
                      <button type="button" className="danger btn-inline" disabled={busy} onClick={() => void removeRow(row)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination-row">
            <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="muted small">
              Page {page} of {totalPages} ({flat.length} versions)
            </span>
            <button
              type="button"
              className="btn-secondary"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
