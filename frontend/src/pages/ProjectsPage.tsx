import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type Project } from "../api";
import { dedupeWorkspacesByName } from "../lib/workspaceList";

/** Matches corpus API tests (`tests/api/test_documents_router.py`); never show in workspace. */
const PYTEST_PROJECT_PREFIX = "__ocean_pytest__";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Project[]>([]);
  const [name, setName] = useState("");
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

  const workspaceProjects = dedupeWorkspacesByName(
    items.filter((p) => !p.name.startsWith(PYTEST_PROJECT_PREFIX)),
  );

  return (
    <div className="page project-route-page">
      <header className="route-header route-header-stack">
        <div>
          <p className="route-kicker">Workspaces</p>
          <h1 className="route-title">Your workspaces</h1>
          <p className="route-lede muted">
            Extract and validate data from supplier PDFs — with pinpoint evidence on every field for QC, AP, and
            audits.
          </p>
        </div>
      </header>
      {actionError ? (
        <p className="alert-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <div className="workspace-create-row">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Riverbank QC Lab"
        />
        <button
          type="button"
          className="btn-primary-lg"
          disabled={!name.trim()}
          onClick={async () => {
            try {
              setActionError(null);
              const p = await api.projects.create(name.trim());
              await load();
              navigate(`/projects/${p.id}`);
            } catch (e: unknown) {
              console.error(e);
              setActionError(e instanceof Error ? e.message : "Create failed");
            }
          }}
        >
          Create workspace
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
                <span className="project-tile-name">{p.name}</span>
                <span className="project-tile-cta">Open workspace →</span>
              </Link>
              <button
                type="button"
                className="project-tile-delete"
                aria-label={`Remove workspace ${p.name}`}
                onClick={async (e) => {
                  e.preventDefault();
                  if (!confirm(`Remove workspace “${p.name}”? This cannot be undone.`)) return;
                  try {
                    setActionError(null);
                    await api.projects.delete(p.id);
                    await load();
                  } catch (err: unknown) {
                    console.error(err);
                    setActionError(err instanceof Error ? err.message : "Remove failed");
                  }
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-panel">
          <p className="empty-panel-title">No workspaces yet</p>
          <p className="muted small">Create one above — e.g. your lab name — then add a document checklist.</p>
        </div>
      )}
    </div>
  );
}
