/**
 * Insights tab — saved cohort views with aggregated PASS/FAIL/AMBIGUOUS stats.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  api,
  type CohortEvaluationOut,
  type CohortFilters,
  type ValidationCohortOut,
  type ValidationSchemaGroupOut,
} from "../api";
import { formatSchemaKey } from "../lib/displayLabels";

const OUTCOMES = ["PASS", "FAIL", "AMBIGUOUS"] as const;

type AttributeFilter = { key: string; value: string | null };

const emptyFilters = (): CohortFilters => ({
  schema_key: null,
  version_label: null,
  outcomes: [],
  attributes: [],
});

export default function ProjectInsightsPage() {
  const { projectId = "" } = useParams();
  const [cohorts, setCohorts] = useState<ValidationCohortOut[]>([]);
  const [schemas, setSchemas] = useState<ValidationSchemaGroupOut[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [filters, setFilters] = useState<CohortFilters>(emptyFilters);
  const [passThreshold, setPassThreshold] = useState(100);
  const [attrKey, setAttrKey] = useState("");
  const [attrValue, setAttrValue] = useState("");
  const [attrKeyOnly, setAttrKeyOnly] = useState(false);
  const [evaluation, setEvaluation] = useState<CohortEvaluationOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCohortId, setSelectedCohortId] = useState<string | null>(null);

  const loadCohorts = useCallback(() => {
    if (!projectId) return;
    api.validation.listCohorts(projectId).then(setCohorts).catch(() => setCohorts([]));
  }, [projectId]);

  useEffect(() => {
    loadCohorts();
    api.validation.listSchemas(projectId).then(setSchemas).catch(() => setSchemas([]));
  }, [projectId, loadCohorts]);

  const versionsForSchema = useMemo(
    () => schemas.find((g) => g.schema_key === filters.schema_key)?.versions ?? [],
    [schemas, filters.schema_key],
  );

  function toggleOutcome(outcome: string) {
    setFilters((prev) => {
      const has = prev.outcomes.includes(outcome);
      return {
        ...prev,
        outcomes: has ? prev.outcomes.filter((o) => o !== outcome) : [...prev.outcomes, outcome],
      };
    });
  }

  function addAttributeFilter() {
    const key = attrKey.trim();
    if (!key) return;
    setFilters((prev) => ({
      ...prev,
      attributes: [
        ...prev.attributes.filter((a) => a.key !== key),
        { key, value: attrKeyOnly ? null : attrValue.trim() || null },
      ],
    }));
    setAttrKey("");
    setAttrValue("");
    setAttrKeyOnly(false);
  }

  function removeAttributeFilter(key: string) {
    setFilters((prev) => ({
      ...prev,
      attributes: prev.attributes.filter((a) => a.key !== key),
    }));
  }

  async function previewEvaluation() {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.validation.evaluateCohort(projectId, {
        name: name || "Preview",
        description: description || null,
        filters,
        pass_threshold_pct: passThreshold,
      });
      setEvaluation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setEvaluation(null);
    } finally {
      setBusy(false);
    }
  }

  async function saveCohort() {
    if (!projectId || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.validation.createCohort(projectId, {
        name: name.trim(),
        description: description.trim() || null,
        filters,
        pass_threshold_pct: passThreshold,
      });
      setSelectedCohortId(created.id);
      loadCohorts();
      await previewEvaluation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadCohort(cohort: ValidationCohortOut) {
    setSelectedCohortId(cohort.id);
    setName(cohort.name);
    setDescription(cohort.description ?? "");
    setFilters(cohort.filters);
    setPassThreshold(cohort.pass_threshold_pct);
    setBusy(true);
    setError(null);
    try {
      const result = await api.validation.evaluateSavedCohort(projectId, cohort.id);
      setEvaluation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteCohort(id: string) {
    if (!projectId) return;
    await api.validation.deleteCohort(projectId, id);
    if (selectedCohortId === id) {
      setSelectedCohortId(null);
      setEvaluation(null);
      setName("");
      setDescription("");
      setFilters(emptyFilters());
    }
    loadCohorts();
  }

  return (
    <div className="page project-route-page insights-page">
      <header className="hero-block">
        <h1 className="hero-title">Insights</h1>
        <p className="hero-sub muted">
          Group validations by tags, checklist, or revision — then see pass rates and drill into matching runs.
        </p>
      </header>

      <div className="insights-layout">
        <aside className="insights-sidebar" aria-label="Saved cohorts">
          <h2 className="section-heading">Saved views</h2>
          {cohorts.length === 0 ? (
            <p className="muted small">No saved views yet. Configure filters and save one.</p>
          ) : (
            <ul className="insights-cohort-list">
              {cohorts.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`insights-cohort-item${selectedCohortId === c.id ? " insights-cohort-item--active" : ""}`}
                    onClick={() => loadCohort(c)}
                  >
                    <span className="insights-cohort-name">{c.name}</span>
                    <span className="muted small">{c.pass_threshold_pct}% pass target</span>
                  </button>
                  <button
                    type="button"
                    className="btn-inline insights-cohort-delete"
                    aria-label={`Delete ${c.name}`}
                    onClick={() => deleteCohort(c.id)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="insights-main" aria-label="Cohort builder">
          <h2 className="section-heading">Build a view</h2>

          <div className="insights-form-grid">
            <label className="field-label">
              <span>Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. March AP batch" />
            </label>
            <label className="field-label">
              <span>Pass threshold (%)</span>
              <input
                type="number"
                min={0}
                max={100}
                value={passThreshold}
                onChange={(e) => setPassThreshold(Number(e.target.value))}
              />
            </label>
            <label className="field-label">
              <span>Checklist</span>
              <select
                value={filters.schema_key ?? ""}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    schema_key: e.target.value || null,
                    version_label: null,
                  }))
                }
              >
                <option value="">Any checklist</option>
                {schemas.map((g) => (
                  <option key={g.schema_key} value={g.schema_key}>
                    {formatSchemaKey(g.schema_key)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              <span>Version</span>
              <select
                value={filters.version_label ?? ""}
                disabled={!filters.schema_key}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, version_label: e.target.value || null }))
                }
              >
                <option value="">Any version</option>
                {versionsForSchema.map((v) => (
                  <option key={v.id} value={v.version_label}>
                    {v.version_label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <fieldset className="insights-outcomes">
            <legend className="section-heading">Outcomes</legend>
            <p className="muted small">Leave all unchecked to include every outcome.</p>
            <div className="insights-outcome-toggles">
              {OUTCOMES.map((o) => (
                <label key={o} className="insights-outcome-toggle">
                  <input
                    type="checkbox"
                    checked={filters.outcomes.includes(o)}
                    onChange={() => toggleOutcome(o)}
                  />
                  <span className={`recent-run-outcome recent-run-outcome--${o.toLowerCase()}`}>{o}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="insights-attr-filters">
            <legend className="section-heading">Tag filters</legend>
            {filters.attributes.length > 0 ? (
              <ul className="validation-attribute-chips">
                {filters.attributes.map((a: AttributeFilter) => (
                  <li key={a.key} className="validation-attribute-chip">
                    <span className="validation-attribute-chip-key">{a.key}</span>
                    {a.value ? (
                      <>
                        <span className="validation-attribute-chip-sep">:</span>
                        <span className="validation-attribute-chip-value">{a.value}</span>
                      </>
                    ) : (
                      <span className="validation-attribute-chip-flag muted small">(flag)</span>
                    )}
                    <button type="button" className="validation-attribute-chip-remove" onClick={() => removeAttributeFilter(a.key)}>
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No tag filters — all tagged runs match.</p>
            )}
            <div className="validation-attribute-add-row">
              <input placeholder="Tag key" value={attrKey} onChange={(e) => setAttrKey(e.target.value)} />
              <input
                placeholder={attrKeyOnly ? "Key-only" : "Value (optional)"}
                value={attrValue}
                disabled={attrKeyOnly}
                onChange={(e) => setAttrValue(e.target.value)}
              />
              <label className="validation-attribute-keyonly">
                <input type="checkbox" checked={attrKeyOnly} onChange={(e) => setAttrKeyOnly(e.target.checked)} />
                <span className="small">Key only</span>
              </label>
              <button type="button" className="btn-secondary" disabled={!attrKey.trim()} onClick={addAttributeFilter}>
                Add filter
              </button>
            </div>
          </fieldset>

          <label className="field-label">
            <span>Description</span>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional note for auditors"
            />
          </label>

          <div className="insights-actions">
            <button type="button" className="btn-secondary" disabled={busy} onClick={previewEvaluation}>
              {busy ? "Loading…" : "Preview results"}
            </button>
            <button type="button" className="btn-primary" disabled={busy || !name.trim()} onClick={saveCohort}>
              Save view
            </button>
          </div>

          {error ? <p className="alert-error" role="alert">{error}</p> : null}

          {evaluation ? (
            <section className="insights-results" aria-label="Cohort results">
              <div
                className={`insights-threshold-banner${evaluation.meets_threshold ? " insights-threshold-banner--ok" : " insights-threshold-banner--fail"}`}
                role="status"
              >
                <strong>{evaluation.pass_rate_pct}%</strong> pass rate
                <span className="muted small">
                  — target {evaluation.pass_threshold_pct}%
                  {evaluation.meets_threshold ? " · meets goal" : " · below goal"}
                </span>
              </div>
              <div className="stat-row insights-stat-row">
                <div className="stat-pill">
                  <span className="stat-pill-value">{evaluation.total}</span>
                  <span className="stat-pill-label">Checked</span>
                </div>
                <div className="stat-pill stat-pill--pass">
                  <span className="stat-pill-value">{evaluation.pass_count}</span>
                  <span className="stat-pill-label">Passed</span>
                </div>
                <div className="stat-pill stat-pill--fail">
                  <span className="stat-pill-value">{evaluation.fail_count}</span>
                  <span className="stat-pill-label">Failed</span>
                </div>
                <div className="stat-pill stat-pill--ambiguous">
                  <span className="stat-pill-value">{evaluation.ambiguous_count}</span>
                  <span className="stat-pill-label">Need review</span>
                </div>
              </div>

              {evaluation.items.length > 0 ? (
                <table className="data-table insights-runs-table">
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Checklist</th>
                      <th>Outcome</th>
                      <th>Tags</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.items.map((r) => (
                      <tr key={r.id}>
                        <td>{r.document_filename}</td>
                        <td className="muted small">
                          {formatSchemaKey(r.schema_key)} · v{r.version_label}
                        </td>
                        <td>
                          <span className={`recent-run-outcome recent-run-outcome--${r.outcome.toLowerCase()}`}>
                            {r.outcome}
                          </span>
                        </td>
                        <td className="muted small">
                          {Object.entries(r.attributes ?? {})
                            .map(([k, v]) => (v ? `${k}: ${v}` : k))
                            .join(", ") || "—"}
                        </td>
                        <td>
                          <Link to={`/projects/${projectId}/validation/runs/${r.id}`}>Open →</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted small">No validations match these filters.</p>
              )}
            </section>
          ) : null}
        </section>
      </div>
    </div>
  );
}
