/**
 * Sample PDF preview validation (temporary pipeline run, not persisted).
 */

import { useRef, useState } from "react";

import type { ValidateDocumentResponse } from "../../api";
import { api } from "../../api";
import { SCHEMA_HELP } from "../../lib/schemaHelp";

export type SchemaDryRunPanelProps = {
  projectId: string;
  jsonText: string;
  jsonInvalid: boolean;
  disabled?: boolean;
  /** ``rail`` hides heading — parent section provides context. */
  variant?: "default" | "rail";
  onPreviewComplete?: (response: ValidateDocumentResponse) => void;
};

export default function SchemaDryRunPanel({
  projectId,
  jsonText,
  jsonInvalid,
  disabled,
  variant = "default",
  onPreviewComplete,
}: SchemaDryRunPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dslErrors, setDslErrors] = useState<string[] | null>(null);
  const [result, setResult] = useState<ValidateDocumentResponse | null>(null);

  const isRail = variant === "rail";

  async function runPreview() {
    if (!file || jsonInvalid || !projectId) return;
    setBusy(true);
    setError(null);
    setDslErrors(null);
    setResult(null);
    try {
      const out = await api.validation.previewSchema(projectId, jsonText, file);
      if (!out.dsl_ok) {
        setDslErrors(out.dsl_errors);
        return;
      }
      if (out.validation) {
        setResult(out.validation);
        onPreviewComplete?.(out.validation);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="schema-dry-run-panel" aria-label="Sample PDF validation">
      {!isRail ? (
        <>
          <h4 className="schema-dry-run-heading">Try on sample PDF</h4>
          <p className="muted small">{SCHEMA_HELP.samplePdf}</p>
        </>
      ) : null}
      <div className="schema-dry-run-row">
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className={`btn-secondary btn-sm ${isRail ? "schema-dry-run-file-btn" : ""}`}
          disabled={disabled || busy}
          onClick={() => fileRef.current?.click()}
        >
          {file ? file.name : "Choose PDF"}
        </button>
        <button
          type="button"
          className="btn-primary btn-sm"
          disabled={disabled || busy || !file || jsonInvalid}
          onClick={() => void runPreview()}
        >
          {busy ? "Validating…" : "Run validation"}
        </button>
      </div>
      {jsonInvalid ? <p className="alert-error small">Fix JSON syntax before validating.</p> : null}
      {error ? (
        <p className="alert-error small" role="alert">
          {error}
        </p>
      ) : null}
      {dslErrors?.length ? (
        <div className="schema-dsl-errors" role="alert">
          <strong>DSL errors</strong>
          <ul>
            {dslErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {result ? (
        <div className={`schema-preview-result schema-preview-result--${result.status.toLowerCase()}`}>
          <p className="schema-preview-status">
            Outcome: <strong>{result.status}</strong>
          </p>
          {result.extraction_meta?.extraction_judge &&
          Array.isArray(result.extraction_meta.extraction_judge) &&
          result.extraction_meta.extraction_judge.length > 0 ? (
            <div className="schema-preview-block">
              <h5>Extraction judge</h5>
              <ul>
                {(result.extraction_meta.extraction_judge as Array<{
                  field: string;
                  approved: boolean;
                  reason: string;
                }>).map((j, i) => (
                  <li key={i}>
                    <code>{j.field}</code> — {j.approved ? "approved" : "rejected"}: {j.reason}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.resolved_values && Object.keys(result.resolved_values).length > 0 ? (
            <div className="schema-preview-block">
              <h5>Extracted</h5>
              <ul className="schema-preview-kv">
                {Object.entries(result.resolved_values).map(([k, v]) => (
                  <li key={k}>
                    <code>{k}</code>: {String(v)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.results.length > 0 ? (
            <div className="schema-preview-block">
              <h5>Validation failures</h5>
              <ul>
                {result.results.map((e, i) => (
                  <li key={i}>
                    <code>{e.field}</code> — {e.rule}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.ambiguous_fields.length > 0 ? (
            <div className="schema-preview-block">
              <h5>Ambiguous</h5>
              <ul>
                {result.ambiguous_fields.map((a) => (
                  <li key={a.field}>
                    <code>{a.field}</code> — {a.candidate_count} candidates
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {(result.open_ended_results?.length ?? 0) > 0 ? (
            <div className="schema-preview-block">
              <h5>Prompt extraction</h5>
              <ul>
                {(result.open_ended_results ?? []).map((oe) => (
                  <li key={oe.field}>
                    <code>{oe.field}</code>
                    {oe.informative_only ? (
                      <span className="muted small"> (informative): {oe.extracted_value ?? "—"}</span>
                    ) : (
                      <span className="muted small"> — {oe.evaluation ?? "—"}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
