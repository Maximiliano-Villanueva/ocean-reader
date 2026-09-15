/**
 * Project home — quick stats, workflow guide, and recent validation activity.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type ValidationRunSummary, type ValidationSchemaGroupOut } from "../api";
import ProjectWelcomeTour from "../components/onboarding/ProjectWelcomeTour";
import { formatSchemaKey } from "../lib/displayLabels";

export default function ProjectOverviewPage() {
  const { projectId = "" } = useParams();
  const [schemas, setSchemas] = useState<ValidationSchemaGroupOut[]>([]);
  const [runTotal, setRunTotal] = useState<number | null>(null);
  const [recentRuns, setRecentRuns] = useState<ValidationRunSummary[]>([]);
  const [outcomeCounts, setOutcomeCounts] = useState({ pass: 0, fail: 0, ambiguous: 0 });

  useEffect(() => {
    if (!projectId) return;
    api.validation.listSchemas(projectId).then(setSchemas).catch(() => setSchemas([]));
    api.validation
      .listRuns(projectId, 1, 1)
      .then((r) => setRunTotal(r.total))
      .catch(() => setRunTotal(null));
    api.validation
      .listRuns(projectId, 1, 8)
      .then((r) => setRecentRuns(r.items))
      .catch(() => setRecentRuns([]));
    Promise.all([
      api.validation.listRuns(projectId, 1, 1, { status: "PASS" }),
      api.validation.listRuns(projectId, 1, 1, { status: "FAIL" }),
      api.validation.listRuns(projectId, 1, 1, { status: "AMBIGUOUS" }),
    ])
      .then(([p, f, a]) =>
        setOutcomeCounts({ pass: p.total, fail: f.total, ambiguous: a.total }),
      )
      .catch(() => setOutcomeCounts({ pass: 0, fail: 0, ambiguous: 0 }));
  }, [projectId]);

  const base = `/projects/${projectId}`;
  const versionCount = schemas.reduce((n, g) => n + g.versions.length, 0);
  const hasChecklists = schemas.length > 0;
  const hasRuns = (runTotal ?? 0) > 0;

  const dashboardStats = [
    {
      to: `${base}/schemas`,
      label: "Checklists",
      value: schemas.length,
      className: "",
      hint: "View all checklists",
    },
    {
      to: `${base}/schemas`,
      label: "Published versions",
      value: versionCount,
      className: "",
      hint: "View checklist versions",
    },
    {
      to: `${base}/validation`,
      label: "Documents checked",
      value: runTotal ?? "—",
      className: "",
      hint: "View validation history",
    },
    {
      to: `${base}/validation?outcome=PASS`,
      label: "Passed",
      value: outcomeCounts.pass,
      className: "stat-pill--pass",
      hint: "View passed validations",
    },
    {
      to: `${base}/validation?outcome=FAIL`,
      label: "Failed",
      value: outcomeCounts.fail,
      className: "stat-pill--fail",
      hint: "View failed validations",
    },
    {
      to: `${base}/validation?outcome=AMBIGUOUS`,
      label: "Need review",
      value: outcomeCounts.ambiguous,
      className: "stat-pill--ambiguous",
      hint: "View ambiguous validations",
    },
  ] as const;

  return (
    <div className="page project-route-page project-overview-page">
      <header className="hero-block project-overview-hero">
        <h1 className="hero-title">Quality dashboard</h1>
        <p className="hero-sub muted">
          Define acceptance rules once, validate PDFs in batch, and export evidence-backed results for auditors and
          finance.
        </p>
      </header>

      <ProjectWelcomeTour
        projectId={projectId}
        base={base}
        hasChecklists={hasChecklists}
        hasRuns={hasRuns}
      />

      <div className="stat-row" role="list" aria-label="Project summary">
        {dashboardStats.map((stat) => (
          <Link
            key={stat.label}
            to={stat.to}
            className={`stat-pill stat-pill--link${stat.className ? ` ${stat.className}` : ""}`}
            aria-label={`${stat.hint} (${stat.value} ${stat.label.toLowerCase()})`}
            role="listitem"
          >
            <span className="stat-pill-value">{stat.value}</span>
            <span className="stat-pill-label">{stat.label}</span>
          </Link>
        ))}
      </div>

      <section className="dashboard-grid" aria-label="Quick access">
        <Link className="dash-card dash-card-accent" to={`${base}/validation/run`}>
          <span className="dash-card-icon" aria-hidden>
            ▶
          </span>
          <span className="dash-card-title">Validate documents</span>
          <span className="dash-card-desc muted">
            Upload one or many PDFs, pick a checklist version, and track progress. Open the full report
            when finished.
          </span>
          <span className="dash-card-cta">
            Start validation <span aria-hidden>→</span>
          </span>
        </Link>
        <Link className="dash-card" to={`${base}/schemas`}>
          <span className="dash-card-icon" aria-hidden>
            📐
          </span>
          <span className="dash-card-title">Checklists</span>
          <span className="dash-card-desc muted">
            Browse document checklists and versions. Create or edit rules with the guided wizard.
          </span>
          <span className="dash-card-cta">
            Manage checklists <span aria-hidden>→</span>
          </span>
        </Link>
        <Link className="dash-card" to={`${base}/validation`}>
          <span className="dash-card-icon" aria-hidden>
            📋
          </span>
          <span className="dash-card-title">History</span>
          <span className="dash-card-desc muted">
            Filter by checklist, outcome, or filename. Re-open any run for fields and PDF highlights.
          </span>
          <span className="dash-card-cta">
            View history <span aria-hidden>→</span>
          </span>
        </Link>
      </section>

      {recentRuns.length > 0 ? (
        <section className="recent-runs-panel" aria-label="Recent validations">
          <div className="recent-runs-head">
            <h2 className="section-heading">Recent validations</h2>
            <Link className="muted small" to={`${base}/validation`}>
              View all →
            </Link>
          </div>
          <ul className="recent-runs-list">
            {recentRuns.map((r) => (
              <li key={r.id}>
                <Link to={`${base}/validation/runs/${r.id}`} className="recent-run-row">
                  <span className="recent-run-name">{r.document_filename}</span>
                  <span className="muted small">
                    {formatSchemaKey(r.schema_key)} · v{r.version_label}
                  </span>
                  <span className={`recent-run-outcome recent-run-outcome--${r.outcome.toLowerCase()}`}>
                    {r.outcome}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
