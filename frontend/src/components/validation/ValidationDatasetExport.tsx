/**
 * Bulk export validation history as CSV / JSON datasets.
 */

import { useCallback, useState } from "react";

import { api, type ValidationRunSummary } from "../../api";
import {
  downloadText,
  validationRunsToCsv,
  validationRunsToJson,
} from "../../lib/exportValidation";

export type ValidationDatasetExportProps = {
  projectId: string;
  projectName?: string;
};

const EXPORT_PAGE_SIZE = 500;

export default function ValidationDatasetExport({
  projectId,
  projectName,
}: ValidationDatasetExportProps) {
  const [busy, setBusy] = useState(false);
  const [lastCount, setLastCount] = useState<number | null>(null);

  const fetchAllRuns = useCallback(async (): Promise<ValidationRunSummary[]> => {
    const first = await api.validation.listRuns(projectId, 1, EXPORT_PAGE_SIZE);
    if (first.total <= EXPORT_PAGE_SIZE) return first.items;
    const second = await api.validation.listRuns(projectId, 2, EXPORT_PAGE_SIZE);
    return [...first.items, ...second.items].slice(0, first.total);
  }, [projectId]);

  const withRuns = useCallback(
    async (fn: (runs: ValidationRunSummary[]) => void) => {
      setBusy(true);
      try {
        const runs = await fetchAllRuns();
        setLastCount(runs.length);
        fn(runs);
      } finally {
        setBusy(false);
      }
    },
    [fetchAllRuns],
  );

  const exportCsv = () =>
    void withRuns((runs) => {
      const slug = (projectName ?? projectId).replace(/[^a-z0-9]+/gi, "-").toLowerCase();
      downloadText(
        `${slug}-validations.csv`,
        validationRunsToCsv(runs),
        "text/csv;charset=utf-8",
      );
    });

  const exportJson = () =>
    void withRuns((runs) => {
      const slug = (projectName ?? projectId).replace(/[^a-z0-9]+/gi, "-").toLowerCase();
      downloadText(
        `${slug}-validations.json`,
        validationRunsToJson(runs, { projectName, projectId }),
        "application/json;charset=utf-8",
      );
    });

  return (
    <section className="export-panel" aria-label="Export datasets">
      <div className="export-panel-head">
        <h2 className="section-heading">Export datasets</h2>
        <p className="muted small">
          Download your validation history for BI tools, auditors, or downstream systems. Up to{" "}
          {EXPORT_PAGE_SIZE} runs per file.
        </p>
      </div>
      <div className="export-panel-actions">
        <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={exportCsv}>
          {busy ? "Preparing…" : "Download CSV"}
        </button>
        <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={exportJson}>
          {busy ? "Preparing…" : "Download JSON"}
        </button>
      </div>
      {lastCount != null ? (
        <p className="muted tiny export-panel-note">Last export: {lastCount} documents</p>
      ) : null}
    </section>
  );
}
