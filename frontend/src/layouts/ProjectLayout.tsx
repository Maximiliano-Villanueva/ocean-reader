import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router-dom";

import { api, type Project } from "../api";

function tabCls({ isActive }: { isActive: boolean }) {
  return isActive ? "project-tab project-tab-active" : "project-tab";
}

/** True on /schemas/new or /schemas/:key/edit — full-screen schema studio. */
function isSchemaStudioRoute(pathname: string) {
  return /\/schemas\/(new|[^/]+\/edit)$/.test(pathname);
}

const TABS = [
  { to: "", end: true, label: "Overview", hint: "Dashboard" },
  { to: "validation", end: true, label: "History", hint: "Audit trail" },
  { to: "validation/run", end: false, label: "Validate", hint: "Upload PDFs" },
  { to: "schemas", end: false, label: "Checklists", hint: "Rules & versions" },
  { to: "insights", end: true, label: "Insights", hint: "Cohorts & tags" },
] as const;

export default function ProjectLayout() {
  const { projectId = "" } = useParams();
  const { pathname } = useLocation();
  const studioMode = isSchemaStudioRoute(pathname);
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    if (!projectId) return;
    api.projects
      .list()
      .then((list) => setProject(list.find((p) => p.id === projectId) ?? null))
      .catch(() => setProject(null));
  }, [projectId]);

  const base = `/projects/${projectId}`;
  const name = project?.name ?? "Loading…";

  return (
    <div className={`project-shell${studioMode ? " project-shell--schema-studio" : ""}`}>
      <div className="project-shell-header">
        <nav className="project-breadcrumb" aria-label="Breadcrumb">
          <Link className="project-crumb-root" to="/projects">
            Workspaces
          </Link>
          <span className="project-crumb-sep" aria-hidden>
            /
          </span>
          <span className="project-crumb-current">{name}</span>
          {studioMode ? (
            <>
              <span className="project-crumb-sep" aria-hidden>
                /
              </span>
              <Link className="project-crumb-link" to={`${base}/schemas`}>
                Checklists
              </Link>
              <span className="project-crumb-sep" aria-hidden>
                /
              </span>
              <span className="project-crumb-current">Editor</span>
            </>
          ) : null}
        </nav>
        {!studioMode ? (
          <nav className="project-tabs" aria-label="Project sections">
            {TABS.map((tab) => (
              <NavLink
                key={tab.label}
                end={tab.end}
                className={tabCls}
                to={tab.to ? `${base}/${tab.to}` : base}
              >
                <span className="project-tab-label">{tab.label}</span>
                <span className="project-tab-hint muted">{tab.hint}</span>
              </NavLink>
            ))}
          </nav>
        ) : null}
      </div>

      <div className="project-shell-body">
        <Outlet />
      </div>
    </div>
  );
}
