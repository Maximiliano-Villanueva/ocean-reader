import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { api, type Project } from "../api";

function tabCls({ isActive }: { isActive: boolean }) {
  return isActive ? "project-tab project-tab-active" : "project-tab";
}

export default function ProjectLayout() {
  const { projectId = "" } = useParams();
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
    <div className="project-shell">
      <div className="project-shell-header">
        <nav className="project-breadcrumb" aria-label="Breadcrumb">
          <Link className="project-crumb-root" to="/projects">
            Projects
          </Link>
          <span className="project-crumb-sep" aria-hidden>
            /
          </span>
          <span className="project-crumb-current">{name}</span>
        </nav>
        <nav className="project-tabs" aria-label="Project sections">
          <NavLink end className={tabCls} to={base}>
            Overview
          </NavLink>
          <NavLink end className={tabCls} to={`${base}/validation`}>
            Validation
          </NavLink>
          <NavLink className={tabCls} to={`${base}/validation/run`}>
            Run
          </NavLink>
          <NavLink className={tabCls} to={`${base}/schemas`}>
            Schemas
          </NavLink>
          <NavLink className={tabCls} to={`${base}/schema-versions`}>
            Versions
          </NavLink>
        </nav>
      </div>

      <div className="project-shell-body">
        <Outlet />
      </div>
    </div>
  );
}
