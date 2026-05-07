import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type ValidationSchemaGroupOut } from "../api";

export default function ProjectOverviewPage() {
  const { projectId = "" } = useParams();
  const [schemas, setSchemas] = useState<ValidationSchemaGroupOut[]>([]);

  useEffect(() => {
    if (!projectId) return;
    api.validation.listSchemas(projectId).then(setSchemas).catch(() => setSchemas([]));
  }, [projectId]);

  const base = `/projects/${projectId}`;

  return (
    <div className="page project-route-page">
      <header className="hero-block">
        <h1 className="hero-title">Project overview</h1>
        <p className="hero-sub muted">
          Schema-driven PDF validation with evidence-first reporting — open Validation to run the pipeline.
        </p>
      </header>

      <div className="stat-row">
        <div className="stat-pill">
          <span className="stat-pill-value">{schemas.length}</span>
          <span className="stat-pill-label">Schema groups</span>
        </div>
      </div>

      <section className="dashboard-grid" aria-label="Quick links">
        <Link className="dash-card dash-card-accent" to={`${base}/validation/run`}>
          <span className="dash-card-icon" aria-hidden>
            ✓
          </span>
          <span className="dash-card-title">Run validation</span>
          <span className="dash-card-desc muted">
            Upload PDFs, pick a schema version, and inspect PASS/FAIL with traceability (text, block id, page,
            bbox). Results persist under Validation history.
          </span>
          <span className="dash-card-cta">
            Open runner <span aria-hidden>→</span>
          </span>
        </Link>
      </section>
    </div>
  );
}
