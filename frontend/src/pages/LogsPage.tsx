import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type LogContainer } from "../api";

export default function LogsPage() {
  const [containers, setContainers] = useState<LogContainer[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [tail, setTail] = useState(400);
  const [logText, setLogText] = useState("");
  const [listError, setListError] = useState<string | null>(null);
  const [tailError, setTailError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingTail, setLoadingTail] = useState(false);

  const refreshContainers = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const rows = await api.logs.listContainers();
      setContainers(rows);
    } catch (e: unknown) {
      setContainers([]);
      setListError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refreshContainers().catch(console.error);
  }, [refreshContainers]);

  useEffect(() => {
    if (!containers.length || selectedId) return;
    const backend = containers.find((r) => r.service === "backend");
    setSelectedId((backend ?? containers[0]).id);
  }, [containers, selectedId]);

  const loadTail = useCallback(async () => {
    if (!selectedId) return;
    setLoadingTail(true);
    setTailError(null);
    try {
      const r = await api.logs.tail(selectedId, tail);
      setLogText(r.text);
    } catch (e: unknown) {
      setLogText("");
      setTailError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingTail(false);
    }
  }, [selectedId, tail]);

  useEffect(() => {
    if (selectedId) {
      loadTail().catch(console.error);
    }
  }, [selectedId, loadTail]);

  return (
    <div className="page">
      <div className="row">
        <Link to="/projects">← Projects</Link>
      </div>
      <h1>Container logs</h1>
      <p className="muted small">
        Docker Compose services for this project (requires log viewer on the API and a mounted Docker socket in Compose).
        Rebuild the frontend if you set <code>VITE_LOG_VIEWER_TOKEN</code> / <code>LOG_VIEWER_TOKEN</code>.
      </p>

      <div className="row wrap">
        <button type="button" onClick={() => refreshContainers()} disabled={loadingList}>
          {loadingList ? "Refreshing…" : "Refresh list"}
        </button>
        <label className="row">
          Container
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            disabled={!containers.length}
          >
            {containers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.service || "?"} — {c.name} ({c.state || c.status})
              </option>
            ))}
          </select>
        </label>
        <label className="row">
          Tail lines
          <input
            type="number"
            min={1}
            max={5000}
            value={tail}
            onChange={(e) => setTail(Number(e.target.value) || 400)}
            style={{ width: "5rem" }}
          />
        </label>
        <button type="button" onClick={() => loadTail()} disabled={loadingTail || !selectedId}>
          {loadingTail ? "Loading…" : "Reload logs"}
        </button>
      </div>

      {listError ? (
        <p className="alert-error" role="alert">
          {listError}
        </p>
      ) : null}
      {tailError ? (
        <p className="alert-error" role="alert">
          {tailError}
        </p>
      ) : null}

      <pre className="trace logs-pre">{logText || (loadingTail ? "…" : "—")}</pre>
    </div>
  );
}
