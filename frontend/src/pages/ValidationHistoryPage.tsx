import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type ValidationRunSummary } from "../api";

const PAGE_SIZE = 25;

export default function ValidationHistoryPage() {
  const { projectId = "" } = useParams();
  const [items, setItems] = useState<ValidationRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.validation.listRuns(projectId, page, PAGE_SIZE);
      setItems(r.items);
      setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [projectId, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page project-route-page validation-history-page">
      <header className="hero-block">
        <h1 className="hero-title">Validation history</h1>
        <p className="hero-sub muted">
          Each row is one persisted run (schema, version, outcome). Open a row for rule-level detail and PDF replay when
          available.
        </p>
        <p className="muted small">
          <Link to={`/projects/${projectId}/validation/run`}>Run new validation</Link>
          {" · "}
          <Link to={`/projects/${projectId}/schemas`}>Schemas</Link>
          {" · "}
          <Link to={`/projects/${projectId}/schema-versions`}>All versions</Link>
        </p>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <div className="empty-panel">
          <p className="empty-panel-title">No validation runs yet</p>
          <p className="muted small">
            Go to <Link to={`/projects/${projectId}/validation/run`}>Run validation</Link> to execute checks — outcomes
            appear here automatically.
          </p>
        </div>
      ) : (
        <>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Schema</th>
                  <th>Version</th>
                  <th>Outcome</th>
                  <th>Started</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.document_filename}</td>
                    <td>
                      <code>{row.schema_key}</code>
                    </td>
                    <td>{row.version_label}</td>
                    <td>
                      <span className={`pill pill-${row.outcome.toLowerCase()}`}>{row.outcome}</span>
                    </td>
                    <td className="muted small">{row.created_at?.replace("T", " ").replace("Z", "") ?? "—"}</td>
                    <td>
                      <Link className="table-action-link" to={`/projects/${projectId}/validation/runs/${row.id}`}>
                        View
                      </Link>
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
              Page {page} of {totalPages} ({total} total)
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
