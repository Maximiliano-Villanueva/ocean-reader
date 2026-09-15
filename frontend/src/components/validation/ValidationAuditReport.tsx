/**
 * Build audit summary markdown from validation history API (for AP / QC reporting).
 */

import { useCallback, useEffect, useState } from "react";

import { api, type ValidationRunSummary } from "../../api";

export type ValidationAuditReportProps = {
  projectId: string;
  projectName?: string;
};

function outcomeLine(runs: ValidationRunSummary[]) {
  const pass = runs.filter((r) => r.outcome === "PASS").length;
  const fail = runs.filter((r) => r.outcome === "FAIL").length;
  const amb = runs.filter((r) => r.outcome === "AMBIGUOUS").length;
  return { pass, fail, amb, total: runs.length };
}

export default function ValidationAuditReport({ projectId, projectName }: ValidationAuditReportProps) {
  const [runs, setRuns] = useState<ValidationRunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api.validation
      .listRuns(projectId, 1, 100)
      .then((r) => setRuns(r.items))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, [projectId]);

  const stats = outcomeLine(runs);
  const generated = new Date().toISOString().replace("T", " ").slice(0, 19);

  const markdown = [
    `# Validation audit summary`,
    ``,
    `**Workspace:** ${projectName ?? projectId}`,
    `**Generated:** ${generated} UTC`,
    ``,
    `## Outcomes`,
    ``,
    `| Result | Count |`,
    `|--------|------:|`,
    `| PASS | ${stats.pass} |`,
    `| FAIL | ${stats.fail} |`,
    `| AMBIGUOUS (needs review) | ${stats.amb} |`,
    `| **Total** | **${stats.total}** |`,
    ``,
    `## Recent documents`,
    ``,
    `| Document | Checklist | Version | Outcome |`,
    `|----------|-----------|---------|---------|`,
    ...runs.slice(0, 25).map(
      (r) =>
        `| ${r.document_filename} | ${r.schema_key} | ${r.version_label} | ${r.outcome} |`,
    ),
    ``,
    `_Each run stores field-level evidence and PDF highlights in Ocean Read history._`,
  ].join("\n");

  const copyReport = useCallback(async () => {
    await navigator.clipboard.writeText(markdown);
  }, [markdown]);

  const downloadReport = useCallback(() => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `validation-audit-${projectId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [markdown, projectId]);

  return (
    <section className="audit-report-panel" aria-label="Audit report">
      <div className="audit-report-head">
        <h2 className="section-heading">Audit report</h2>
        <p className="muted small">
          Summary for leadership or external auditors — copy or download Markdown.
        </p>
      </div>
      {loading ? (
        <p className="muted small">Loading run statistics…</p>
      ) : (
        <>
          <div className="audit-report-stats">
            <span className="audit-stat audit-stat--pass">{stats.pass} passed</span>
            <span className="audit-stat audit-stat--fail">{stats.fail} failed</span>
            <span className="audit-stat audit-stat--amb">{stats.amb} need review</span>
          </div>
          <div className="audit-report-actions">
            <button type="button" className="btn-secondary btn-sm" onClick={() => void copyReport()}>
              Copy to clipboard
            </button>
            <button type="button" className="btn-primary btn-sm" onClick={downloadReport}>
              Download .md
            </button>
          </div>
          <details className="audit-report-preview">
            <summary className="muted small">Preview</summary>
            <pre className="audit-report-pre">{markdown}</pre>
          </details>
        </>
      )}
    </section>
  );
}
