/**
 * Validation run detail: field extraction table + PDF evidence (user-friendly layout).
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import PdfEvidenceViewer from "../components/pdf/PdfEvidenceViewer";
import RunExportActions from "../components/validation/RunExportActions";
import RunFieldCorrectionEditor from "../components/validation/RunFieldCorrectionEditor";
import { formatRunTimestamp } from "../lib/formatDate";
import { formatSchemaKey } from "../lib/displayLabels";
import RunFieldExtractionTable from "../components/validation/RunFieldExtractionTable";
import RunOpenEndedTable from "../components/validation/RunOpenEndedTable";
import RunSchemaOverview from "../components/validation/RunSchemaOverview";
import { api, type ValidationRunDetailOut } from "../api";
import {
  highlightsFromOpenEnded,
  highlightsFromPipelineSnapshot,
  highlightsFromReport,
  mergeHighlights,
  refineReportHighlightsWithBlocks,
  type PdfHighlight,
  type PipelineBlock,
  type PipelineCandidate,
} from "../lib/evidenceHighlights";
import { buildRunFieldRows } from "../lib/runFieldRows";
import { describeValidationRule, outcomeSummary } from "../lib/ruleDescriptions";

export default function ValidationRunDetailPage() {
  const { projectId = "", runId = "" } = useParams();
  const [run, setRun] = useState<ValidationRunDetailOut | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [candidates, setCandidates] = useState<PipelineCandidate[]>([]);
  const [blocks, setBlocks] = useState<PipelineBlock[]>([]);
  const [snapshotHighlights, setSnapshotHighlights] = useState<PdfHighlight[]>([]);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  const [correctionMode, setCorrectionMode] = useState(false);

  useEffect(() => {
    if (!projectId || !runId) return;
    let cancelled = false;
    setError(null);
    api.validation
      .getRun(projectId, runId)
      .then((r) => {
        if (!cancelled) setRun(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, runId]);

  useEffect(() => {
    if (!projectId || !runId || !run?.has_pdf) return;
    let cancelled = false;
    let blobUrl: string | null = null;
    api.validation.fetchRunPdfObjectUrl(projectId, runId).then((u) => {
      if (!cancelled && u) {
        blobUrl = u;
        setPdfUrl(u);
      }
    });
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [projectId, runId, run?.has_pdf]);

  useEffect(() => {
    if (!projectId || !runId || !run) return;
    let cancelled = false;
    void (async () => {
      try {
        const [cands, blocks] = await Promise.all([
          api.validation.fetchRunCandidates(projectId, runId),
          api.validation.fetchRunBlocks(projectId, runId),
        ]);
        if (!cancelled) {
          setCandidates(cands);
          setBlocks(blocks);
          setSnapshotHighlights(highlightsFromPipelineSnapshot(run.report, cands, blocks));
        }
      } catch {
        if (!cancelled) {
          setCandidates([]);
          setBlocks([]);
          setSnapshotHighlights([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, runId, run]);

  const openEndedResults = run?.report.open_ended_results ?? [];

  const pdfHighlights = useMemo(() => {
    if (!run) return [] as PdfHighlight[];
    const oe = highlightsFromOpenEnded(run.report.open_ended_results);
    const fromReport = refineReportHighlightsWithBlocks(
      highlightsFromReport(run.report),
      blocks,
      run.report,
    );
    return mergeHighlights(mergeHighlights(fromReport, snapshotHighlights), oe);
  }, [run, snapshotHighlights, blocks]);

  function highlightIdForOpenEnded(field: string, blockId: string, page: number): string | null {
    const match = pdfHighlights.find(
      (h) => h.field === field && h.id.includes(blockId) && h.page === page,
    );
    return match?.id ?? pdfHighlights.find((h) => h.field === field)?.id ?? null;
  }

  const fieldRows = useMemo(() => {
    if (!run) return [];
    return buildRunFieldRows(run.report.schema_snapshot ?? null, run.report, candidates, pdfHighlights);
  }, [run, candidates, pdfHighlights]);

  const failedRules = useMemo(() => {
    if (!run) return [];
    const outcomes = run.report.field_rule_outcomes ?? [];
    const fromOutcomes = outcomes.filter((o) => !o.passed);
    if (fromOutcomes.length > 0) return fromOutcomes;
    return (run.report.results ?? []).map((r) => ({
      field: r.field,
      rule: r.rule,
      passed: false,
      value: r.value,
      expected: r.expected,
      evidence: r.evidence,
    }));
  }, [run]);

  function jumpToHighlight(highlightId: string) {
    setActiveHighlightId(highlightId);
  }

  function jumpToField(field: string) {
    const row = fieldRows.find((r) => r.field === field);
    const id = row?.highlightIds[0] ?? row?.candidates[0]?.highlightId;
    if (id) setActiveHighlightId(id);
  }

  if (error) {
    return (
      <div className="page project-route-page validation-run-detail-page">
        <p className="alert-error">{error}</p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="page project-route-page validation-run-detail-page">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  const report = run.report;
  const outcomeClass = `run-outcome-banner run-outcome-banner--${run.outcome.toLowerCase()}`;

  return (
    <div className="page project-route-page validation-run-detail-page">
      <nav className="muted small run-detail-nav">
        <Link to={`/projects/${projectId}/validation`}>← Validation history</Link>
      </nav>

      {(run.archived_at || run.deleted_at) && (
        <div className="validation-run-lifecycle-banner" role="status">
          <p className="muted small">
            {run.deleted_at
              ? "Removed from default history (audit copy kept)."
              : "Archived — hidden from default list."}
          </p>
          <button
            type="button"
            className="btn-secondary btn-sm"
            disabled={lifecycleBusy}
            onClick={async () => {
              setLifecycleBusy(true);
              try {
                await api.validation.patchRunLifecycle(projectId, runId, { restore: true });
                setRun(await api.validation.getRun(projectId, runId));
              } catch (e: unknown) {
                setError(e instanceof Error ? e.message : String(e));
              } finally {
                setLifecycleBusy(false);
              }
            }}
          >
            Restore to history
          </button>
        </div>
      )}

      <div className="run-detail-layout">
        <div className="run-detail-main">
          <header className="run-detail-header">
            <div className="run-detail-header-main">
              <h1 className="run-detail-title">{run.document_filename}</h1>
              <p className="muted small">
                {formatSchemaKey(run.schema_key)} · version {run.version_label}
                {run.revision_number && run.revision_number > 1 ? ` · revision ${run.revision_number}` : ""}
                {run.created_at ? ` · ${formatRunTimestamp(run.created_at)}` : ""}
              </p>
              {run.parent_run_id ? (
                <p className="muted small">
                  Corrected from{" "}
                  <Link to={`/projects/${projectId}/validation/runs/${run.parent_run_id}`}>previous run</Link>
                </p>
              ) : null}
            </div>
            <div className={outcomeClass} role="status">
              <span className="run-outcome-label">{run.outcome}</span>
              <span className="run-outcome-desc muted small">{outcomeSummary(report.status)}</span>
            </div>
          </header>

          {run.outcome === "FAIL" ? (
            <p className="run-outcome-explainer run-outcome-explainer--fail" role="note">
              <strong>Failed</strong> — at least one required field is missing, out of range, or breaks a checklist rule.
              Review the table below and use <em>View →</em> on each row to jump to evidence on the PDF.
            </p>
          ) : null}

          {run.outcome === "AMBIGUOUS" ? (
            <p className="run-outcome-explainer run-outcome-explainer--ambiguous" role="note">
              <strong>Needs review</strong> — conflicting readings were found for one or more fields. Compare candidates
              in the table and on the PDF before approving.
            </p>
          ) : null}

          {report.extraction_meta?.vision_fallback_used === true && (
            <p className="validation-run-vision-banner muted small" role="note">
              This run used <strong>vision extraction</strong>: page images were sent to the LLM because the PDF had
              little or no selectable text (common for scans).
            </p>
          )}

          <RunExportActions run={run} fieldRows={fieldRows} />

          <section className="run-detail-panel" aria-labelledby="run-fields-heading">
            <div className="run-detail-panel-head">
              <h2 id="run-fields-heading" className="section-heading">
                Extracted fields
              </h2>
              {!correctionMode ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  disabled={fieldRows.length === 0}
                  onClick={() => setCorrectionMode(true)}
                >
                  Correct values
                </button>
              ) : null}
            </div>
            <p className="muted small run-detail-panel-hint">
              Each value is tied to evidence on the PDF. Click a row to highlight the exact source in the document.
            </p>
            {correctionMode ? (
              <RunFieldCorrectionEditor
                projectId={projectId}
                runId={runId}
                revisionNumber={run.revision_number ?? 1}
                fieldRows={fieldRows}
                onCancel={() => setCorrectionMode(false)}
              />
            ) : (
              <RunFieldExtractionTable
                rows={fieldRows}
                activeHighlightId={activeHighlightId}
                onJumpToHighlight={jumpToHighlight}
              />
            )}
          </section>

          {openEndedResults.length > 0 ? (
            <section className="run-detail-panel" aria-labelledby="run-open-ended-heading">
              <h2 id="run-open-ended-heading" className="section-heading">
                Open-ended (LLM) fields
              </h2>
              <p className="muted small run-detail-panel-hint">
                Prompt-based extraction and evaluation. Informative fields do not change PASS/FAIL.
              </p>
              <RunOpenEndedTable
                rows={openEndedResults}
                activeHighlightId={activeHighlightId}
                onJumpToHighlight={jumpToHighlight}
                highlightIdForEvidence={highlightIdForOpenEnded}
              />
            </section>
          ) : null}

          {failedRules.length > 0 ? (
            <section className="run-detail-panel" aria-labelledby="run-failures-heading">
              <h2 id="run-failures-heading" className="section-heading">
                Rule violations
              </h2>
              <ul className="run-failures-list">
                {failedRules.map((o, i) => (
                  <li key={`${o.field}-${o.rule}-${i}`}>
                    <button
                      type="button"
                      className="run-failure-chip"
                      onClick={() => jumpToField(o.field)}
                    >
                      <strong>{o.field}</strong>
                      <span className="muted"> — {describeValidationRule(o.rule)}</span>
                      <span className="run-failure-jump">Show on PDF →</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <RunSchemaOverview
            schemaSnapshot={report.schema_snapshot ?? null}
            schemaKey={run.schema_key}
            versionLabel={run.version_label}
          />

          <details className="run-detail-technical">
            <summary className="muted small">Run metadata</summary>
            <dl className="run-meta-dl muted small">
              <dt>Run id</dt>
              <dd>
                <code>{run.id}</code>
              </dd>
              {run.pdf_hash ? (
                <>
                  <dt>PDF fingerprint</dt>
                  <dd>
                    <code className="pdf-hash-code">{run.pdf_hash}</code>
                  </dd>
                </>
              ) : null}
            </dl>
            {!(run.archived_at || run.deleted_at) ? (
              <p className="muted small">
                <button
                  type="button"
                  className="btn-inline link-button"
                  disabled={lifecycleBusy}
                  onClick={async () => {
                    setLifecycleBusy(true);
                    try {
                      await api.validation.patchRunLifecycle(projectId, runId, { archived: true });
                      setRun(await api.validation.getRun(projectId, runId));
                    } catch (e: unknown) {
                      setError(e instanceof Error ? e.message : String(e));
                    } finally {
                      setLifecycleBusy(false);
                    }
                  }}
                >
                  Archive
                </button>
                {" · "}
                <button
                  type="button"
                  className="btn-inline link-button"
                  disabled={lifecycleBusy}
                  onClick={async () => {
                    if (!window.confirm("Remove from default history?")) return;
                    setLifecycleBusy(true);
                    try {
                      await api.validation.softDeleteRun(projectId, runId);
                      setRun(await api.validation.getRun(projectId, runId));
                    } catch (e: unknown) {
                      setError(e instanceof Error ? e.message : String(e));
                    } finally {
                      setLifecycleBusy(false);
                    }
                  }}
                >
                  Remove
                </button>
              </p>
            ) : null}
          </details>
        </div>

        <aside className="run-detail-pdf-pane" aria-label="Document with highlights">
          <div className="run-detail-pdf-sticky">
            <h2 className="section-heading run-detail-pdf-title">Source document</h2>
            {pdfUrl ? (
              <PdfEvidenceViewer
                file={pdfUrl}
                highlights={pdfHighlights}
                activeHighlightId={activeHighlightId}
                onHighlightClick={(h) => setActiveHighlightId(h.id)}
                className="run-pdf-viewer"
              />
            ) : run.has_pdf ? (
              <p className="muted">Loading PDF…</p>
            ) : (
              <p className="muted">No PDF stored for this run.</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
