/**
 * Inline correction editor for validation run extracted fields.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../../api";
import type { RunFieldRow } from "../../lib/runFieldRows";
import { formatFieldLabel } from "../../lib/displayLabels";

type Props = {
  projectId: string;
  runId: string;
  revisionNumber: number;
  fieldRows: RunFieldRow[];
  onCancel: () => void;
};

/** Edit extracted values and save as a new revalidated run revision. */
export default function RunFieldCorrectionEditor({
  projectId,
  runId,
  revisionNumber,
  fieldRows,
  onCancel,
}: Props) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const row of fieldRows) {
      if (row.extractedSummary && row.extractedSummary !== "—") {
        initial[row.field] = row.extractedSummary;
      }
    }
    return initial;
  });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changedFields = useMemo(() => {
    const out: Record<string, string> = {};
    for (const row of fieldRows) {
      const current = draft[row.field];
      if (current === undefined) continue;
      if (current !== row.extractedSummary) {
        out[row.field] = current;
      }
    }
    return out;
  }, [draft, fieldRows]);

  const hasChanges = Object.keys(changedFields).length > 0;

  async function onSave() {
    if (!hasChanges) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.validation.createRunRevision(projectId, runId, {
        corrections: changedFields,
        note: note.trim() || undefined,
      });
      navigate(`/projects/${projectId}/validation/runs/${created.id}`, { replace: true });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="run-correction-panel" aria-labelledby="run-correction-heading">
      <header className="run-correction-head">
        <div>
          <h2 id="run-correction-heading" className="section-heading">
            Correct extracted values
          </h2>
          <p className="muted small">
            Saving creates revision {revisionNumber + 1} and re-checks PASS / FAIL / AMBIGUOUS against the checklist.
          </p>
        </div>
        <div className="run-correction-actions">
          <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary-lg btn-sm"
            disabled={busy || !hasChanges}
            onClick={() => void onSave()}
          >
            {busy ? "Saving…" : "Save revision"}
          </button>
        </div>
      </header>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="run-correction-fields">
        {fieldRows.map((row) => (
          <label key={row.field} className="run-correction-field field-label">
            <span>{formatFieldLabel(row.field)}</span>
            <input
              type="text"
              value={draft[row.field] ?? ""}
              onChange={(e) => setDraft((prev) => ({ ...prev, [row.field]: e.target.value }))}
              disabled={busy}
              aria-describedby={`${row.field}-expected`}
            />
            <span id={`${row.field}-expected`} className="muted small run-field-expected" title={row.expectedSummary}>
              Expected: {row.expectedSummary}
            </span>
          </label>
        ))}
      </div>

      <label className="field-label run-correction-note">
        <span className="muted small">Audit note (optional)</span>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="e.g. Lab confirmed correct reading on retest"
          disabled={busy}
        />
      </label>
    </section>
  );
}
