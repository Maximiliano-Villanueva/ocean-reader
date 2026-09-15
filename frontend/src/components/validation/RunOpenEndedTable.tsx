/**
 * Table of open-ended (LLM) extraction results with optional PDF jump links.
 */

import type { OpenEndedFieldResultOut } from "../../api";

export type RunOpenEndedTableProps = {
  rows: OpenEndedFieldResultOut[];
  activeHighlightId: string | null;
  onJumpToHighlight: (highlightId: string) => void;
  /** Map field+block to highlight id from merged PDF highlights. */
  highlightIdForEvidence: (field: string, blockId: string, page: number) => string | null;
};

export default function RunOpenEndedTable({
  rows,
  activeHighlightId,
  onJumpToHighlight,
  highlightIdForEvidence,
}: RunOpenEndedTableProps) {
  if (rows.length === 0) return null;

  return (
    <div className="run-fields-table-wrap table-scroll">
      <table className="data-table run-fields-table run-open-ended-table">
        <thead>
          <tr>
            <th scope="col">Open field</th>
            <th scope="col">Extracted</th>
            <th scope="col">Evaluation</th>
            <th scope="col">Role</th>
            <th scope="col" className="run-fields-pdf-col">
              PDF
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const primaryEv = row.evidence[0];
            const hid = primaryEv
              ? highlightIdForEvidence(row.field, primaryEv.block_id, primaryEv.page)
              : null;
            const active = hid != null && activeHighlightId === hid;
            const evalLabel = row.informative_only
              ? "Informative"
              : row.evaluation
                ? row.evaluation.toUpperCase()
                : "—";
            const evalClass = row.informative_only
              ? "run-field-status run-field-status--not_evaluated"
              : row.evaluation === "pass"
                ? "run-field-status run-field-status--resolved"
                : row.evaluation === "fail"
                  ? "run-field-status run-field-status--failed"
                  : "run-field-status run-field-status--ambiguous";
            return (
              <tr
                key={row.field}
                className={`run-field-row ${hid ? "run-field-row--clickable" : ""} ${active ? "run-field-row--active" : ""}`}
                onClick={() => hid && onJumpToHighlight(hid)}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && hid) {
                    e.preventDefault();
                    onJumpToHighlight(hid);
                  }
                }}
                tabIndex={hid ? 0 : undefined}
                role={hid ? "button" : undefined}
              >
                <td>
                  <span className="run-field-name">{row.field}</span>
                </td>
                <td>
                  <strong>{row.extracted_value ?? "—"}</strong>
                  {row.evidence[0]?.text ? (
                    <span className="run-field-evidence-quote muted small"> “{row.evidence[0].text.slice(0, 120)}…”</span>
                  ) : null}
                </td>
                <td>
                  <span className={`run-field-status ${evalClass}`}>{evalLabel}</span>
                </td>
                <td className="muted small">{row.informative_only ? "Does not affect PASS/FAIL" : "Can affect outcome"}</td>
                <td className="run-fields-pdf-col">
                  {hid ? (
                    <span className="run-field-pdf-link">View →</span>
                  ) : (
                    <span className="muted small">No link</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
