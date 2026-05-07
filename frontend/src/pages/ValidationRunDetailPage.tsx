import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type ValidationRunDetailOut } from "../api";
import { describeValidationRule, outcomeSummary } from "../lib/ruleDescriptions";

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function ValidationRunDetailPage() {
  const { projectId = "", runId = "" } = useParams();
  const [run, setRun] = useState<ValidationRunDetailOut | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
  const outcomes = report.field_rule_outcomes ?? [];
  const hasLedger = outcomes.length > 0;
  const resolved = report.resolved_values;
  const snapshot = report.schema_snapshot;

  return (
    <div className="page project-route-page validation-run-detail-page">
      <nav className="muted small" aria-label="Back navigation">
        <Link to={`/projects/${projectId}/validation`}>← Validation history</Link>
      </nav>

      <header className="hero-block">
        <h1 className="hero-title">{run.document_filename}</h1>
        <p className="hero-sub muted">
          Run record: schema <code>{run.schema_key}</code> · label {run.version_label}
        </p>
        <p className="muted small">
          Applied for validation: <code>{report.schema_id}</code> · version{" "}
          <code>{report.schema_version}</code>
        </p>
        <p className={`validation-status validation-status-${run.outcome.toLowerCase()}`} role="status">
          {run.outcome}
        </p>
        <p className="muted small">{outcomeSummary(report.status)}</p>
      </header>

      <div className="validation-result-layout validation-result-layout--detail">
        <div className="validation-result-main">
          <section className="validation-detail-section">
            <h2 className="section-heading">Applied schema (snapshot)</h2>
            <p className="muted small">
              Immutable JSON body used for this run. Compare <code>schema_id</code> /{" "}
              <code>schema_version</code> above with your version list if needed.
            </p>
            {snapshot && Object.keys(snapshot).length > 0 ? (
              <details open>
                <summary className="muted small">Schema definition</summary>
                <pre className="schema-json-view" role="region" aria-label="Applied schema JSON">
                  {formatJson(snapshot)}
                </pre>
              </details>
            ) : (
              <p className="muted small">
                No schema snapshot stored for this run (older history rows only store summary metadata).
              </p>
            )}
          </section>

          <section className="validation-detail-section">
            <h2 className="section-heading">Extracted values</h2>
            <p className="muted small">Resolved field values after extraction (when the pipeline reached validation).</p>
            {resolved && Object.keys(resolved).length > 0 ? (
              <table className="validation-ledger-table">
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    <th scope="col">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(resolved).map(([k, v]) => (
                    <tr key={k}>
                      <td>
                        <code>{k}</code>
                      </td>
                      <td>
                        <code>{formatJson(v)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted small">
                {report.status === "AMBIGUOUS"
                  ? "Values were not uniquely resolved — see ambiguous fields below."
                  : "No resolved values on record for this run (legacy row or pipeline stopped earlier)."}
              </p>
            )}
          </section>

          <section className="validation-detail-section">
            <h2 className="section-heading">Rule ledger</h2>
            <p className="muted small">
              Every global rule evaluated per field (<code>required</code>, <code>type_check</code>,{" "}
              <code>range_validation</code>). Includes passes and failures.
            </p>
            {report.status === "AMBIGUOUS" && (report.ambiguous_fields?.length ?? 0) > 0 ? (
              <p className="validation-ambiguous-note">
                Ambiguous fields:{" "}
                {(report.ambiguous_fields ?? []).map((a) => `${a.field} (${a.candidate_count} candidates)`).join(", ")}
              </p>
            ) : null}

            {hasLedger ? (
              <div className="validation-ledger-wrap">
                <table className="validation-ledger-table">
                  <thead>
                    <tr>
                      <th scope="col">Field</th>
                      <th scope="col">Rule</th>
                      <th scope="col">Result</th>
                      <th scope="col">Extracted</th>
                      <th scope="col">Expected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outcomes.map((o, i) => (
                      <tr key={`${o.field}-${o.rule}-${i}`}>
                        <td>
                          <code>{o.field}</code>
                        </td>
                        <td>
                          <span className="muted">{describeValidationRule(o.rule)}</span>
                          <br />
                          <code className="muted small">{o.rule}</code>
                        </td>
                        <td>
                          <span
                            className={`validation-file-queue-badge ${
                              o.passed ? "validation-file-queue-badge--pass" : "validation-file-queue-badge--fail"
                            }`}
                          >
                            {o.passed ? "Pass" : "Fail"}
                          </span>
                        </td>
                        <td>
                          <code>{o.value === undefined || o.value === null ? "—" : formatJson(o.value)}</code>
                        </td>
                        <td>
                          <code>{o.expected === undefined || o.expected === null ? "—" : formatJson(o.expected)}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {outcomes.some((o) => o.evidence) ? (
                  <div className="validation-ledger-evidence-block">
                    <h3 className="section-heading validation-ledger-evidence-heading">Evidence by row</h3>
                    <ul className="list validation-error-list">
                      {outcomes.map((o, i) =>
                        o.evidence ? (
                          <li key={`ev-${o.field}-${o.rule}-${i}`} className="validation-error-card">
                            <div className="validation-error-title">
                              <strong>{o.field}</strong>
                              <span className="muted"> · {describeValidationRule(o.rule)}</span>
                            </div>
                            <dl className="evidence-dl">
                              <dt>Evidence text</dt>
                              <dd>
                                <pre className="evidence-snippet">{o.evidence.text || "—"}</pre>
                              </dd>
                              <dt>Placement</dt>
                              <dd>
                                Block <code>{o.evidence.block_id || "—"}</code> · page {o.evidence.page}
                              </dd>
                            </dl>
                          </li>
                        ) : null,
                      )}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : report.results.length > 0 ? (
              <ul className="list validation-error-list">
                {report.results.map((r) => (
                  <li key={`${r.field}-${r.rule}`} className="validation-error-card">
                    <div className="validation-error-title">
                      <strong>{r.field}</strong>
                      <span className="muted"> · {describeValidationRule(r.rule)}</span>
                    </div>
                    <p className="muted small rule-meta">
                      Rule code <code>{r.rule}</code> · extracted value: <code>{String(r.value)}</code> · expected:{" "}
                      <code>{JSON.stringify(r.expected)}</code>
                    </p>
                    {r.evidence ? (
                      <dl className="evidence-dl">
                        <dt>Evidence text</dt>
                        <dd>
                          <pre className="evidence-snippet">{r.evidence.text || "—"}</pre>
                        </dd>
                        <dt>Placement</dt>
                        <dd>
                          Block <code>{r.evidence.block_id || "—"}</code> · page {r.evidence.page}
                        </dd>
                      </dl>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : report.status === "AMBIGUOUS" ? (
              <p className="muted small">
                No per-rule ledger on record for this run (older persisted ambiguous runs may omit it).
              </p>
            ) : (
              <p className="muted">
                No per-rule ledger stored for this run — only the overall outcome is available. Re-validate the
                document to capture a full pass/fail breakdown.
              </p>
            )}
          </section>
        </div>
        <aside className="validation-pdf-pane" aria-label="PDF replay">
          {pdfUrl ? (
            <iframe title={`PDF: ${run.document_filename}`} src={pdfUrl} className="pdf-frame" />
          ) : run.has_pdf ? (
            <p className="muted">Loading PDF…</p>
          ) : (
            <p className="muted">No PDF was stored for this run.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
