/**
 * Export extracted fields and full validation report for a single run.
 */

import { useCallback } from "react";

import type { ValidationRunDetailOut } from "../../api";
import { downloadText, runDetailToJson, runExtractionToCsv } from "../../lib/exportValidation";
import type { RunFieldRow } from "../../lib/runFieldRows";

export type RunExportActionsProps = {
  run: ValidationRunDetailOut;
  fieldRows: RunFieldRow[];
};

export default function RunExportActions({ run, fieldRows }: RunExportActionsProps) {
  const stem = run.document_filename.replace(/\.pdf$/i, "") || "document";

  const exportCsv = useCallback(() => {
    downloadText(
      `${stem}-extraction.csv`,
      runExtractionToCsv(run, fieldRows),
      "text/csv;charset=utf-8",
    );
  }, [run, fieldRows, stem]);

  const exportJson = useCallback(() => {
    downloadText(
      `${stem}-validation.json`,
      runDetailToJson(run, fieldRows),
      "application/json;charset=utf-8",
    );
  }, [run, fieldRows, stem]);

  const copyJson = useCallback(async () => {
    await navigator.clipboard.writeText(runDetailToJson(run, fieldRows));
  }, [run, fieldRows]);

  return (
    <section className="export-bar" aria-label="Export results">
      <div className="export-bar-copy">
        <h2 className="export-bar-title">Export this result</h2>
        <p className="muted small">
          Share extracted fields with finance, ERP, or your audit folder — CSV for spreadsheets, JSON for
          integrations.
        </p>
      </div>
      <div className="export-bar-actions">
        <button type="button" className="btn-secondary btn-sm" onClick={exportCsv}>
          CSV fields
        </button>
        <button type="button" className="btn-secondary btn-sm" onClick={exportJson}>
          JSON report
        </button>
        <button type="button" className="btn-ghost btn-sm" onClick={() => void copyJson()}>
          Copy JSON
        </button>
      </div>
    </section>
  );
}
