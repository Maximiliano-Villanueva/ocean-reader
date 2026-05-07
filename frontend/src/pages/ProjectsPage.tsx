import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type Project } from "../api";

/** Matches corpus API tests (`tests/api/test_documents_router.py`); never show in workspace. */
const PYTEST_PROJECT_PREFIX = "__ocean_pytest__";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Project[]>([]);
  const [name, setName] = useState("New project");
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setActionError(null);
    setItems(await api.projects.list());
  }, []);

  useEffect(() => {
    load().catch((e: unknown) => {
      console.error(e);
      setActionError(e instanceof Error ? e.message : "Failed to load projects");
    });
  }, [load]);

  const workspaceProjects = items.filter((p) => !p.name.startsWith(PYTEST_PROJECT_PREFIX));

  return (
    <div className="page project-route-page">
      <header className="route-header route-header-stack">
        <div>
          <p className="route-kicker">Workspace</p>
          <h1 className="route-title">Projects</h1>
          <p className="route-lede muted">Create a project, then pick a section from the tab bar inside it.</p>
        </div>
      </header>
      {actionError ? (
        <p className="alert-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <div className="row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" />
        <button
          type="button"
          className="btn-primary-lg"
          onClick={async () => {
            try {
              setActionError(null);
              const p = await api.projects.create(name);
              await load();
              navigate(`/projects/${p.id}`);
            } catch (e: unknown) {
              console.error(e);
              setActionError(e instanceof Error ? e.message : "Create failed");
            }
          }}
        >
          Create project
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() =>
            load().catch((e: unknown) => {
              console.error(e);
              setActionError(e instanceof Error ? e.message : "Failed to load projects");
            })
          }
        >
          Refresh
        </button>
      </div>
      {workspaceProjects.length ? (
        <ul className="projects-catalog" role="list">
          {workspaceProjects.map((p) => (
            <li key={p.id} className="project-catalog-item">
              <Link className="project-tile" to={`/projects/${p.id}`}>
                {p.name}
              </Link>
              <button
                type="button"
                className="danger"
                aria-label={`Delete ${p.name}`}
                onClick={async () => {
                  if (!confirm("Delete project?")) return;
                  try {
                    setActionError(null);
                    await api.projects.delete(p.id);
                    await load();
                  } catch (e: unknown) {
                    console.error(e);
                    setActionError(e instanceof Error ? e.message : "Delete failed");
                  }
                }}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-panel">
          <p className="empty-panel-title">No projects yet</p>
          <p className="muted small">Create one above to open the Overview dashboard.</p>
        </div>
      )}
    </div>
  );
}
