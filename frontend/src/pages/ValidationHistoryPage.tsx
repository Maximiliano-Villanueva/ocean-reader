import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import ValidationReRunDialog from "../components/validation/ValidationReRunDialog";
import {
  api,
  type ValidationRunSummary,
  type ValidationSchemaGroupOut,
} from "../api";

const PAGE_SIZE = 25;

const OUTCOME_FILTERS = ["", "PASS", "FAIL", "AMBIGUOUS"] as const;

export default function ValidationHistoryPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const [schemaGroups, setSchemaGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [items, setItems] = useState<ValidationRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSchemaKey, setFilterSchemaKey] = useState("");
  const [filterVersionLabel, setFilterVersionLabel] = useState("");
  const [filterOutcome, setFilterOutcome] = useState("");
  const [documentSearchInput, setDocumentSearchInput] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reRunTarget, setReRunTarget] = useState<ValidationRunSummary | null>(null);

  useEffect(() => {
    if (!projectId) return;
    api.validation
      .listSchemas(projectId)
      .then(setSchemaGroups)
      .catch(() => setSchemaGroups([]));
  }, [projectId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDocumentSearch(documentSearchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [documentSearchInput]);

  const versionOptions = useMemo(() => {
    if (!filterSchemaKey) return [];
    const g = schemaGroups.find((x) => x.schema_key === filterSchemaKey);
    return g?.versions ?? [];
  }, [schemaGroups, filterSchemaKey]);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.validation.listRuns(projectId, page, PAGE_SIZE, {
        schemaKey: filterSchemaKey || undefined,
        versionLabel: filterVersionLabel || undefined,
        documentContains: documentSearch || undefined,
        status: filterOutcome || undefined,
        includeHidden: showHidden ? true : undefined,
      });
      setItems(r.items);
      setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [projectId, page, filterSchemaKey, filterVersionLabel, documentSearch, filterOutcome, showHidden]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const hasActiveFilters =
    Boolean(filterSchemaKey || filterVersionLabel || filterOutcome || documentSearch);

  const onFilterSchemaChange = (value: string) => {
    setFilterSchemaKey(value);
    setFilterVersionLabel("");
    setPage(1);
  };

  const onFilterVersionChange = (value: string) => {
    setFilterVersionLabel(value);
    setPage(1);
  };

  const onFilterOutcomeChange = (value: string) => {
    setFilterOutcome(value);
    setPage(1);
  };

  const clearFilters = () => {
    setFilterSchemaKey("");
    setFilterVersionLabel("");
    setFilterOutcome("");
    setDocumentSearchInput("");
    setDocumentSearch("");
    setPage(1);
  };

  const withBusy = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    try {
      await fn();
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onArchive = (runId: string) =>
    void withBusy(runId, () => api.validation.patchRunLifecycle(projectId, runId, { archived: true }));

  const onRemove = (runId: string) => {
    if (!window.confirm("Remove this run from the default history? You can show hidden runs and restore it later.")) {
      return;
    }
    void withBusy(runId, () => api.validation.softDeleteRun(projectId, runId));
  };

  const onRestore = (runId: string) =>
    void withBusy(runId, () => api.validation.patchRunLifecycle(projectId, runId, { restore: true }));

  return (
    <div className="page project-route-page validation-history-page">
      <header className="hero-block">
        <h1 className="hero-title">Validation history</h1>
        <p className="hero-sub muted">
          Each row is one persisted run. Filter by schema, version, or document name. Re-run stores a{" "}
          <strong>new</strong> result when you change schema or version.
        </p>
        <p className="muted small">
          <Link to={`/projects/${projectId}/validation/run`}>Run new validation</Link>
          {" · "}
          <Link to={`/projects/${projectId}/schemas`}>Schemas</Link>
        </p>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <div className="validation-history-filters" aria-label="Filter runs">
            <label className="field-label validation-filter-field">
              <span className="muted small">Document name contains</span>
              <input
                type="search"
                value={documentSearchInput}
                onChange={(e) => setDocumentSearchInput(e.target.value)}
                placeholder="e.g. syn_amb or row_003"
                aria-label="Search document filename"
              />
            </label>
            <label className="field-label validation-filter-field">
              <span className="muted small">Schema</span>
              <select
                value={filterSchemaKey}
                onChange={(e) => onFilterSchemaChange(e.target.value)}
                aria-label="Filter by schema key"
              >
                <option value="">All schemas</option>
                {schemaGroups.map((g) => (
                  <option key={g.schema_key} value={g.schema_key}>
                    {g.schema_key}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label validation-filter-field">
              <span className="muted small">Version</span>
              <select
                value={filterVersionLabel}
                onChange={(e) => onFilterVersionChange(e.target.value)}
                disabled={!filterSchemaKey}
                aria-label="Filter by schema version"
              >
                <option value="">{filterSchemaKey ? "All versions" : "Select schema first"}</option>
                {versionOptions.map((v) => (
                  <option key={v.id} value={v.version_label}>
                    {v.version_label} ({v.status})
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label validation-filter-field">
              <span className="muted small">Outcome</span>
              <select
                value={filterOutcome}
                onChange={(e) => onFilterOutcomeChange(e.target.value)}
                aria-label="Filter by outcome"
              >
                {OUTCOME_FILTERS.map((o) => (
                  <option key={o || "all"} value={o}>
                    {o === "" ? "All outcomes" : o}
                  </option>
                ))}
              </select>
            </label>
            {hasActiveFilters ? (
              <button type="button" className="btn-secondary validation-filter-clear" onClick={clearFilters}>
                Clear filters
              </button>
            ) : null}
            <label className="field-label validation-filter-field validation-filter-checkbox">
              <input
                type="checkbox"
                checked={showHidden}
                onChange={(e) => {
                  setShowHidden(e.target.checked);
                  setPage(1);
                }}
              />
              <span className="muted small">Show archived / removed</span>
            </label>
          </div>

          {items.length === 0 ? (
            <div className="empty-panel">
              <p className="empty-panel-title">
                {hasActiveFilters ? "No runs match these filters" : "No validation runs yet"}
              </p>
              <p className="muted small">
                {hasActiveFilters ? (
                  <>
                    Adjust filters or{" "}
                    <button type="button" className="btn-inline link-button" onClick={clearFilters}>
                      clear them
                    </button>
                    .
                  </>
                ) : (
                  <>
                    Go to <Link to={`/projects/${projectId}/validation/run`}>Run validation</Link> to execute checks.
                  </>
                )}
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
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => {
                      const hidden = Boolean(row.archived_at || row.deleted_at);
                      const isBusy = busyId === row.id;
                      return (
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
                          <td className="validation-run-status-cell muted small">
                            {row.deleted_at ? (
                              <span className="pill pill-muted" title={row.deleted_at}>
                                Removed
                              </span>
                            ) : null}
                            {row.archived_at ? (
                              <span className="pill pill-muted" title={row.archived_at}>
                                Archived
                              </span>
                            ) : null}
                            {!hidden ? "—" : null}
                          </td>
                          <td className="validation-run-actions-cell">
                            <Link className="table-action-link" to={`/projects/${projectId}/validation/runs/${row.id}`}>
                              View
                            </Link>
                            <button
                              type="button"
                              className="btn-inline link-button validation-run-row-action"
                              disabled={isBusy || busyId !== null || schemaGroups.length === 0}
                              title={
                                schemaGroups.length === 0
                                  ? "Create a schema before re-running"
                                  : "Validate stored PDF with another schema/version"
                              }
                              onClick={() => {
                                if (schemaGroups.length === 0) {
                                  setError("No schemas available — create one under Schemas first.");
                                  return;
                                }
                                setReRunTarget(row);
                              }}
                            >
                              Re-run
                            </button>
                            {hidden ? (
                              <button
                                type="button"
                                className="btn-inline link-button validation-run-row-action"
                                disabled={isBusy}
                                onClick={() => onRestore(row.id)}
                              >
                                Restore
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  className="btn-inline link-button validation-run-row-action"
                                  disabled={isBusy}
                                  onClick={() => onArchive(row.id)}
                                >
                                  Archive
                                </button>
                                <button
                                  type="button"
                                  className="btn-inline link-button validation-run-row-action"
                                  disabled={isBusy}
                                  onClick={() => onRemove(row.id)}
                                >
                                  Remove
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      );
                    })}
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
        </>
      )}

      {reRunTarget && schemaGroups.length > 0 ? (
        <ValidationReRunDialog
          projectId={projectId}
          run={reRunTarget}
          schemaGroups={schemaGroups}
          onClose={() => setReRunTarget(null)}
          onSuccess={(newRunId) => {
            setReRunTarget(null);
            void load();
            navigate(`/projects/${projectId}/validation/runs/${newRunId}`);
          }}
          onError={setError}
        />
      ) : null}
    </div>
  );
}
