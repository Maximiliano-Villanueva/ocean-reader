import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  api,
  type ValidateDocumentResponse,
  type ValidationSchemaGroupOut,
} from "../api";
import ValidationAttributePicker, { type RunAttribute } from "../components/validation/ValidationAttributePicker";
import { formatSchemaKey } from "../lib/displayLabels";

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
  const [error, setError] = useState<string | null>(null);
  const [schemaLoadError, setSchemaLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [attributes, setAttributes] = useState<RunAttribute[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setSchemaKey("");
    setVersion("");
    setGroups([]);
    setSchemaLoadError(null);
    setQueue([]);
    setAttributes([]);
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

  const anyRunning = queue.some((q) => q.phase === "running");
  const completedCount = queue.filter((q) => q.phase === "done").length;
  const passCount = queue.filter((q) => q.result?.status === "PASS").length;
  const failCount = queue.filter((q) => q.result?.status === "FAIL").length;
  const ambCount = queue.filter((q) => q.result?.status === "AMBIGUOUS").length;
  const errorCount = queue.filter((q) => q.phase === "done" && q.error).length;
  const batchDone = queue.length > 0 && completedCount === queue.length && !anyRunning;

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
  }, []);

  const clearQueue = useCallback(() => {
    setQueue([]);
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

  const attributeMap = useMemo(() => {
    const out: Record<string, string | null> = {};
    for (const a of attributes) {
      const k = a.key.trim();
      if (!k) continue;
      out[k] = a.value?.trim() ? a.value.trim() : null;
    }
    return out;
  }, [attributes]);

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
          const r = await api.validation.validateDocument(
            projectId,
            schemaKey,
            version,
            entry.file,
            attributeMap,
          );
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

  return (
    <div className="page project-route-page validation-page">
      <header className="hero-block validation-page-hero">
        <h1 className="hero-title">Validate documents</h1>
        <p className="hero-sub muted">
          Upload PDFs, run them against your checklist, and open each result to see exactly what was extracted — with
          highlights on the source document.
        </p>
        <p className="muted small validation-page-hero-links">
          Manage rules under <Link to={`/projects/${projectId}/schemas`}>Checklists</Link>.
          Past runs live in <Link to={`/projects/${projectId}/validation`}>History</Link>.
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
            <span>Checklist</span>
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
                  {formatSchemaKey(g.schema_key)}
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

        <ValidationAttributePicker
          projectId={projectId}
          value={attributes}
          onChange={setAttributes}
          disabled={busy}
        />

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

        {batchDone && queue.length > 1 ? (
          <p className="validation-batch-summary" role="status">
            <strong>Batch complete:</strong> {passCount} passed · {failCount} failed · {ambCount} need review
            {errorCount > 0 ? ` · ${errorCount} errors` : ""}
          </p>
        ) : null}

        {queue.length > 0 && (
          <div className="validation-file-queue" aria-live="polite">
            <div className="validation-file-queue-header">
              <span className="muted small">
                {anyRunning
                  ? `Validating… (${completedCount}/${queue.length} done)`
                  : `${queue.length} PDF${queue.length === 1 ? "" : "s"} in queue`}
              </span>
              <button type="button" className="btn-inline validation-file-queue-clear" onClick={clearQueue}>
                Clear all
              </button>
            </div>
            <ul className="list validation-file-queue-list validation-run-status-list">
              {queue.map((q) => (
                <li key={q.key} className="validation-run-status-item">
                  <div className="validation-run-status-row">
                    <span className="validation-file-queue-name">{q.file.name}</span>
                    {q.phase === "idle" && <span className="validation-run-phase muted small">Queued</span>}
                    {q.phase === "running" && (
                      <span className="validation-run-phase validation-run-phase--running">In progress…</span>
                    )}
                    {q.phase === "done" && q.error && (
                      <span className="validation-file-queue-badge validation-file-queue-badge--error">Error</span>
                    )}
                    {q.phase === "done" && q.result && (
                      <span
                        className={`validation-file-queue-badge validation-file-queue-badge--${q.result.status.toLowerCase()}`}
                      >
                        {q.result.status}
                      </span>
                    )}
                  </div>
                  {q.phase === "done" && q.result?.run_id ? (
                    <Link
                      to={`/projects/${projectId}/validation/runs/${q.result.run_id}`}
                      className="validation-run-detail-link"
                    >
                      View full report with PDF highlights →
                    </Link>
                  ) : null}
                  {q.phase === "done" && q.error ? (
                    <p className="alert-error small" role="alert">
                      {q.error}
                    </p>
                  ) : null}
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
    </div>
  );
}
