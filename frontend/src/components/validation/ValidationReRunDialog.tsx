/**
 * Re-validate a stored run's PDF against a different schema key / revision (new run).
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api, type ValidationRunSummary, type ValidationSchemaGroupOut } from "../../api";

export type ValidationReRunDialogProps = {
  projectId: string;
  run: ValidationRunSummary;
  schemaGroups: ValidationSchemaGroupOut[];
  onClose: () => void;
  onSuccess: (newRunId: string) => void;
  onError: (message: string) => void;
};

export default function ValidationReRunDialog({
  projectId,
  run,
  schemaGroups,
  onClose,
  onSuccess,
  onError,
}: ValidationReRunDialogProps) {
  const [schemaKey, setSchemaKey] = useState(run.schema_key);
  const [versionLabel, setVersionLabel] = useState(run.version_label);
  const [busy, setBusy] = useState(false);

  const versionsForSchema = useMemo(() => {
    const g = schemaGroups.find((x) => x.schema_key === schemaKey);
    return g?.versions ?? [];
  }, [schemaGroups, schemaKey]);

  useEffect(() => {
    const labels = versionsForSchema.map((v) => v.version_label);
    if (labels.length && !labels.includes(versionLabel)) {
      const active = versionsForSchema.find((v) => v.status.toLowerCase() === "active");
      setVersionLabel(active?.version_label ?? labels[0]!);
    }
  }, [versionsForSchema, versionLabel]);

  async function onSubmit() {
    if (!schemaKey.trim() || !versionLabel.trim()) {
      onError("Choose a schema and version.");
      return;
    }
    setBusy(true);
    try {
      const file = await api.validation.fetchRunPdfAsFile(
        projectId,
        run.id,
        run.document_filename || "document.pdf",
      );
      if (!file) {
        onError("PDF is not stored for this run — upload the file again from Run validation.");
        return;
      }
      const result = await api.validation.validateDocument(
        projectId,
        schemaKey.trim(),
        versionLabel.trim(),
        file,
      );
      if (!result.run_id) {
        onError("Validation finished but no run id was returned.");
        return;
      }
      onSuccess(result.run_id);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="validation-rerun-backdrop" role="presentation" onClick={onClose}>
      <div
        className="validation-rerun-dialog"
        role="dialog"
        aria-labelledby="validation-rerun-title"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="validation-rerun-header">
          <h2 id="validation-rerun-title">Re-run with different schema</h2>
          <p className="muted small">
            Creates a <strong>new</strong> validation run for{" "}
            <code>{run.document_filename}</code>. The original run ({run.schema_key} @ {run.version_label}) is
            unchanged.
          </p>
        </header>

        <div className="validation-rerun-form">
          <label className="field-label">
            <span>Schema</span>
            <select value={schemaKey} onChange={(e) => setSchemaKey(e.target.value)} disabled={busy}>
              {schemaGroups.map((g) => (
                <option key={g.schema_key} value={g.schema_key}>
                  {g.schema_key}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            <span>Version</span>
            <select
              value={versionLabel}
              onChange={(e) => setVersionLabel(e.target.value)}
              disabled={busy || versionsForSchema.length === 0}
            >
              {versionsForSchema.map((v) => (
                <option key={v.id} value={v.version_label}>
                  {v.version_label} ({v.status})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="validation-rerun-actions row">
          <button type="button" className="btn-primary-lg" disabled={busy} onClick={() => void onSubmit()}>
            {busy ? "Running…" : "Run validation"}
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>

        <p className="muted tiny validation-rerun-foot">
          Or <Link to={`/projects/${projectId}/validation/run`}>upload a new file</Link>.
        </p>
      </div>
    </div>
  );
}
