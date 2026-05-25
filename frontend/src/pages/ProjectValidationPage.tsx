import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  api,
  type ValidateDocumentResponse,
  type ValidationSchemaGroupOut,
} from "../api";
import PdfEvidenceViewer from "../components/pdf/PdfEvidenceViewer";
import {
  highlightsFromPipelineSnapshot,
  highlightsFromReport,
  mergeHighlights,
  type PdfHighlight,
} from "../lib/evidenceHighlights";

function isPdfFile(f: File): boolean {
  const lower = f.name.toLowerCase();
  if (!lower.endsWith(".pdf")) return false;
  const t = (f.type || "").toLowerCase();
  return t === "" || t === "application/pdf" || t === "application/x-pdf";
}

function fileKey(f: File): string {
  return `${f.name}:${f.size}:${f.lastModified}`;
}

type QueueEntry = {
  key: string;
  file: File;
  /** After a run: outcome for this file */
  result?: ValidateDocumentResponse;
  error?: string;
  phase: "idle" | "running" | "done";
};

export default function ProjectValidationPage() {
  const { projectId = "" } = useParams();
  const [groups, setGroups] = useState<ValidationSchemaGroupOut[]>([]);
  const [schemaKey, setSchemaKey] = useState("");
  const [version, setVersion] = useState("");
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [schemaLoadError, setSchemaLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [candidateHighlights, setCandidateHighlights] = useState<PdfHighlight[]>([]);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);

  useEffect(() => {
    setSchemaKey("");
    setVersion("");
    setGroups([]);
    setSchemaLoadError(null);
    setQueue([]);
    setActiveKey(null);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setSchemaLoadError(null);
    api.validation
      .listSchemas(projectId)
      .then((g) => {
        if (!cancelled) {
          setGroups(g);
          setSchemaLoadError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setGroups([]);
          setSchemaLoadError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (groups.length === 0 || schemaKey) return;
    const g0 = groups[0]!;
    setSchemaKey(g0.schema_key);
    const pick = g0.versions.find((v) => v.status === "active") ?? g0.versions[0];
    if (pick) setVersion(pick.version_label);
  }, [groups, schemaKey]);

  const activeEntry = useMemo(() => queue.find((q) => q.key === activeKey) ?? null, [queue, activeKey]);

  const versionsForKey = useMemo(
    () => groups.find((g) => g.schema_key === schemaKey)?.versions ?? [],
    [groups, schemaKey],
  );

  const addPdfFiles = useCallback((incoming: File[]) => {
    const pdfs = incoming.filter(isPdfFile);
    if (pdfs.length === 0) return;
    setQueue((prev) => {
      const seen = new Set(prev.map((p) => fileKey(p.file)));
      const next = [...prev];
      for (const file of pdfs) {
        const k = fileKey(file);
        if (seen.has(k)) continue;
        seen.add(k);
        next.push({ key: crypto.randomUUID(), file, phase: "idle" });
      }
      return next;
    });
    setError(null);
  }, []);

  const removeFromQueue = useCallback((key: string) => {
    setQueue((prev) => prev.filter((q) => q.key !== key));
    setActiveKey((cur) => (cur === key ? null : cur));
  }, []);

  const clearQueue = useCallback(() => {
    setQueue([]);
    setActiveKey(null);
    setError(null);
  }, []);

  const preventDefaults = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const onDragEnter = useCallback(
    (e: React.DragEvent) => {
      preventDefaults(e);
      dragDepth.current += 1;
      setDragActive(true);
    },
    [preventDefaults],
  );

  const onDragLeave = useCallback(
    (e: React.DragEvent) => {
      preventDefaults(e);
      dragDepth.current -= 1;
      if (dragDepth.current <= 0) {
        dragDepth.current = 0;
        setDragActive(false);
      }
    },
    [preventDefaults],
  );

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      preventDefaults(e);
      setDragActive(true);
    },
    [preventDefaults],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      preventDefaults(e);
      dragDepth.current = 0;
      setDragActive(false);
      const list: File[] = [];
      if (e.dataTransfer.files?.length) {
        for (let i = 0; i < e.dataTransfer.files.length; i++) {
          list.push(e.dataTransfer.files[i]!);
        }
      }
      addPdfFiles(list);
      if (list.length && !list.some(isPdfFile)) {
        setError("Only PDF files are accepted.");
      }
    },
    [addPdfFiles, preventDefaults],
  );

  useEffect(() => {
    if (queue.length === 0) {
      setActiveKey(null);
      return;
    }
    setActiveKey((cur) => {
      if (cur && queue.some((q) => q.key === cur)) return cur;
      return queue[0]!.key;
    });
  }, [queue]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const snapshot = queue;
    if (snapshot.length === 0 || !schemaKey || !version) return;
    setBusy(true);
    setError(null);
    setQueue((prev) => prev.map((q) => ({ ...q, phase: "idle" as const, result: undefined, error: undefined })));
    try {
      for (let i = 0; i < snapshot.length; i++) {
        const entry = snapshot[i]!;
        const key = entry.key;
        setQueue((prev) =>
          prev.map((q) => (q.key === key ? { ...q, phase: "running", result: undefined, error: undefined } : q)),
        );
        try {
          const r = await api.validation.validateDocument(projectId, schemaKey, version, entry.file);
          setQueue((prev) => prev.map((q) => (q.key === key ? { ...q, phase: "done", result: r } : q)));
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          setQueue((prev) => prev.map((q) => (q.key === key ? { ...q, phase: "done", error: msg } : q)));
        }
      }
    } finally {
      setBusy(false);
    }
  }

  const result = activeEntry?.result;

  useEffect(() => {
    const runId = result?.run_id;
    if (!projectId || !runId) {
      setCandidateHighlights([]);
      return;
    }
    let cancelled = false;
    void Promise.all([
      api.validation.fetchRunCandidates(projectId, runId),
      api.validation.fetchRunBlocks(projectId, runId),
    ]).then(([cands, blocks]) => {
      if (!cancelled && result) {
        setCandidateHighlights(highlightsFromPipelineSnapshot(result, cands, blocks));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [projectId, result]);

  const pdfHighlights = useMemo(() => {
    if (!result) return [] as PdfHighlight[];
    return mergeHighlights(highlightsFromReport(result), candidateHighlights);
  }, [result, candidateHighlights]);

  return (
    <div className="page project-route-page validation-page">
      <header className="hero-block">
        <h1 className="hero-title">Run validation</h1>
        <p className="hero-sub muted">
          Drag PDFs, choose an active schema version, then run the pipeline. Results are saved to{" "}
          <Link to={`/projects/${projectId}/validation`}>validation history</Link>.
        </p>
        <p className="muted small">
          Manage rule definitions under <Link to={`/projects/${projectId}/schemas`}>Schemas</Link> or{" "}
          <Link to={`/projects/${projectId}/schema-versions`}>All versions</Link>.
        </p>
      </header>

      {schemaLoadError ? (
        <p className="alert-error" role="alert">
          {schemaLoadError}
          {schemaLoadError.includes("404") ? (
            <span className="muted small">
              {" "}
              — Project missing from DB (wrong URL or wiped volume). Pick a project from the workspace list.
            </span>
          ) : null}
        </p>
      ) : null}

      <form className="validation-form" onSubmit={onSubmit}>
        <div className="validation-form-grid">
          <label className="field-label">
            <span>Schema</span>
            <select
              value={schemaKey}
              onChange={(e) => {
                setSchemaKey(e.target.value);
                setVersion("");
              }}
            >
              <option value="">Select…</option>
              {groups.map((g) => (
                <option key={g.schema_key} value={g.schema_key}>
                  {g.schema_key}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            <span>Version</span>
            <select value={version} onChange={(e) => setVersion(e.target.value)} disabled={!schemaKey}>
              <option value="">Select…</option>
              {versionsForKey.map((v) => (
                <option key={v.id} value={v.version_label}>
                  {v.version_label} ({v.status})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div
          className={`validation-dropzone${dragActive ? " validation-dropzone--active" : ""}`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          role="region"
          aria-label="PDF drop zone"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="validation-dropzone-input"
            onChange={(e) => {
              const list = e.target.files ? Array.from(e.target.files) : [];
              addPdfFiles(list);
              e.target.value = "";
            }}
          />
          <p className="validation-dropzone-title">Drop PDFs here</p>
          <p className="validation-dropzone-hint muted small">
            Multiple files supported. Non-PDF files are ignored.
          </p>
          <button type="button" className="btn-secondary validation-dropzone-browse" onClick={() => fileInputRef.current?.click()}>
            Add files…
          </button>
        </div>

        {queue.length > 0 && (
          <div className="validation-file-queue" aria-live="polite">
            <div className="validation-file-queue-header">
              <span className="muted small">{queue.length} PDF{queue.length === 1 ? "" : "s"} queued</span>
              <button type="button" className="btn-inline validation-file-queue-clear" onClick={clearQueue}>
                Clear all
              </button>
            </div>
            <ul className="list validation-file-queue-list">
              {queue.map((q) => (
                <li key={q.key} className="validation-file-queue-item">
                  <button
                    type="button"
                    className={`validation-file-queue-select${activeKey === q.key ? " validation-file-queue-select--active" : ""}`}
                    onClick={() => setActiveKey(q.key)}
                  >
                    <span className="validation-file-queue-name">{q.file.name}</span>
                    {q.phase === "running" && <span className="muted small">Running…</span>}
                    {q.phase === "done" && q.result && (
                      <span className={`validation-file-queue-badge validation-file-queue-badge--${q.result.status.toLowerCase()}`}>
                        {q.result.status}
                      </span>
                    )}
                    {q.phase === "done" && q.error && <span className="validation-file-queue-badge validation-file-queue-badge--error">Error</span>}
                  </button>
                  <button
                    type="button"
                    className="validation-file-queue-remove"
                    aria-label={`Remove ${q.file.name}`}
                    onClick={() => removeFromQueue(q.key)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <button type="submit" className="btn-primary-lg" disabled={busy || queue.length === 0 || !schemaKey || !version}>
          {busy ? "Validating…" : queue.length > 1 ? `Run validation (${queue.length} files)` : "Run validation"}
        </button>
      </form>

      {error && <p className="alert-error">{error}</p>}

      {activeEntry && (activeEntry.result || activeEntry.error) && (
        <div className="validation-result-layout">
          <div className="validation-result-main">
            {activeEntry.error ? (
              <p className="alert-error" role="alert">
                {activeEntry.file.name}: {activeEntry.error}
              </p>
            ) : activeEntry.result ? (
              <>
                <p className="muted small">
                  <strong>{activeEntry.file.name}</strong>
                </p>
                <p
                  className={`validation-status validation-status-${activeEntry.result.status.toLowerCase()}`}
                  role="status"
                  aria-live="polite"
                >
                  {activeEntry.result.status}
                </p>
                <p className="muted small">
                  Schema <code>{activeEntry.result.schema_id}</code> @ {activeEntry.result.schema_version}
                </p>
                {activeEntry.result.status === "AMBIGUOUS" && (activeEntry.result.ambiguous_fields?.length ?? 0) > 0 && (
                  <p className="validation-ambiguous-note">
                    Ambiguous fields (multiple conflicting extractions):{" "}
                    <strong>
                      {(activeEntry.result.ambiguous_fields ?? []).map((a) => `${a.field} (${a.candidate_count})`).join(", ")}
                    </strong>
                  </p>
                )}
                {activeEntry.result.results.length > 0 ? (
                  <ul className="list validation-error-list">
                    {activeEntry.result.results.map((r) => (
                      <li key={`${r.field}-${r.rule}`} className="validation-error-card">
                        <div className="validation-error-title">
                          <strong>{r.field}</strong>{" "}
                          <span className="muted">
                            ({r.rule}) value={String(r.value)} expected={JSON.stringify(r.expected)}
                          </span>
                        </div>
                        {r.evidence && (
                          <>
                            <button
                              type="button"
                              className="evidence-jump-btn evidence-jump-btn--inline"
                              onClick={() => {
                                const hit = pdfHighlights.find(
                                  (h) => h.field === r.field && h.rule === r.rule,
                                );
                                if (hit) setActiveHighlightId(hit.id);
                              }}
                            >
                              Show on PDF
                            </button>
                            <dl className="evidence-dl">
                              <dt>Evidence text</dt>
                              <dd>
                                <pre className="evidence-snippet">{r.evidence.text || "—"}</pre>
                              </dd>
                              <dt>Block / page</dt>
                              <dd>
                                <code>{r.evidence.block_id || "—"}</code> · page {r.evidence.page}
                                {r.evidence.bbox && r.evidence.bbox.length >= 4 ? (
                                  <>
                                    {" "}
                                    · bbox [{r.evidence.bbox.map((n) => n.toFixed(1)).join(", ")}]
                                  </>
                                ) : null}
                              </dd>
                            </dl>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : activeEntry.result.status !== "AMBIGUOUS" ? (
                  <p className="muted">No rule violations.</p>
                ) : null}
              </>
            ) : null}
          </div>
          <aside className="validation-pdf-pane" aria-label="PDF preview">
            {activeEntry ? (
              <PdfEvidenceViewer
                file={activeEntry.file}
                highlights={pdfHighlights}
                activeHighlightId={activeHighlightId}
                onHighlightClick={(h) => setActiveHighlightId(h.id)}
              />
            ) : (
              <p className="muted">Select a queued file to preview.</p>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
