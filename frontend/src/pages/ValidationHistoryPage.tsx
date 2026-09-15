import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import ValidationAuditReport from "../components/validation/ValidationAuditReport";
import ValidationDatasetExport from "../components/validation/ValidationDatasetExport";
import ValidationOutcomeGuide from "../components/validation/ValidationOutcomeGuide";
import ValidationReRunDialog from "../components/validation/ValidationReRunDialog";
import ValidationRunRowActions from "../components/validation/ValidationRunRowActions";
import { formatSchemaKey } from "../lib/displayLabels";
import { formatRunTimestamp } from "../lib/formatDate";
import {
  api,
  type Project,
  type ValidationRunSummary,
  type ValidationSchemaGroupOut,
} from "../api";

const PAGE_SIZE = 25;

const OUTCOME_FILTERS = ["", "PASS", "FAIL", "AMBIGUOUS"] as const;

export default function ValidationHistoryPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [schemaGroups, setSchemaGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [items, setItems] = useState<ValidationRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSchemaKey, setFilterSchemaKey] = useState("");
  const [filterVersionLabel, setFilterVersionLabel] = useState("");
  const [filterOutcome, setFilterOutcome] = useState(() => {
    const fromUrl = searchParams.get("outcome") ?? "";
    return OUTCOME_FILTERS.includes(fromUrl as (typeof OUTCOME_FILTERS)[number]) ? fromUrl : "";
  });
  const [documentSearchInput, setDocumentSearchInput] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reRunTarget, setReRunTarget] = useState<ValidationRunSummary | null>(null);
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    const fromUrl = searchParams.get("outcome") ?? "";
    const next = OUTCOME_FILTERS.includes(fromUrl as (typeof OUTCOME_FILTERS)[number]) ? fromUrl : "";
    setFilterOutcome((current) => (current === next ? current : next));
    setPage(1);
  }, [searchParams]);

  const updateOutcomeFilter = useCallback(
    (value: string) => {
      setFilterOutcome(value);
      setPage(1);
      const next = new URLSearchParams(searchParams);
      if (value) {
        next.set("outcome", value);
      } else {
        next.delete("outcome");
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    if (!projectId) return;
    api.projects
      .list()
      .then((list) => setProject(list.find((p) => p.id === projectId) ?? null))
      .catch(() => setProject(null));
  }, [projectId]);

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

  const showLifecycleColumn = showHidden || items.some((row) => row.archived_at || row.deleted_at);

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
    updateOutcomeFilter(value);
  };

  const clearFilters = () => {
    setFilterSchemaKey("");
    setFilterVersionLabel("");
    updateOutcomeFilter("");
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
          Every checked document is stored here with its outcome and checklist version — your audit trail.
        </p>
        <p className="muted small">
          <Link to={`/projects/${projectId}/validation/run`}>Validate new documents</Link>
          {" · "}
          <Link to={`/projects/${projectId}/schemas`}>Checklists</Link>
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
              <span className="muted small">Checklist</span>
              <select
                value={filterSchemaKey}
                onChange={(e) => onFilterSchemaChange(e.target.value)}
                aria-label="Filter by checklist"
              >
                <option value="">All checklists</option>
                {schemaGroups.map((g) => (
                  <option key={g.schema_key} value={g.schema_key}>
                    {formatSchemaKey(g.schema_key)}
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
                aria-label="Filter by checklist version"
              >
                <option value="">{filterSchemaKey ? "All versions" : "Select checklist first"}</option>
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
                      <th>Checklist</th>
                      <th>Version</th>
                      <th>Outcome</th>
                      <th>Started</th>
                      {showLifecycleColumn ? <th>Status</th> : null}
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
                            <span className="checklist-label" title={row.schema_key}>
                              {formatSchemaKey(row.schema_key)}
                            </span>
                          </td>
                          <td>{row.version_label}</td>
                          <td>
                            <span className={`pill pill-${row.outcome.toLowerCase()}`}>{row.outcome}</span>
                          </td>
                          <td className="muted small validation-run-started-cell">
                            {formatRunTimestamp(row.created_at)}
                          </td>
                          {showLifecycleColumn ? (
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
                          ) : null}
                          <td className="validation-run-actions-cell">
                            <ValidationRunRowActions
                              projectId={projectId}
                              row={row}
                              hidden={hidden}
                              isBusy={isBusy}
                              canReRun={schemaGroups.length > 0}
                              onReRun={() => {
                                if (schemaGroups.length === 0) {
                                  setError("No checklists available — create one under Checklists first.");
                                  return;
                                }
                                setReRunTarget(row);
                              }}
                              onArchive={() => onArchive(row.id)}
                              onRemove={() => onRemove(row.id)}
                              onRestore={() => onRestore(row.id)}
                            />
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

      <section className="history-reports-stack" aria-labelledby="history-reports-heading">
        <h2 id="history-reports-heading" className="section-label history-reports-heading">
          Reports &amp; exports
        </h2>
        <ValidationOutcomeGuide />
        <ValidationDatasetExport projectId={projectId} projectName={project?.name} />
        <ValidationAuditReport projectId={projectId} projectName={project?.name} />
      </section>

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
