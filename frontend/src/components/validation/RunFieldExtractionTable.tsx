/**
 * Clickable table: schema expectations vs what was extracted, linked to PDF highlights.
 */

import type { RunFieldRow } from "../../lib/runFieldRows";
import { formatFieldLabel } from "../../lib/displayLabels";

export type RunFieldExtractionTableProps = {
  rows: RunFieldRow[];
  activeHighlightId: string | null;
  onJumpToHighlight: (highlightId: string) => void;
};

export default function RunFieldExtractionTable({
  rows,
  activeHighlightId,
  onJumpToHighlight,
}: RunFieldExtractionTableProps) {
  if (rows.length === 0) {
    return <p className="muted small">No fields defined in the schema snapshot for this run.</p>;
  }

  return (
    <div className="run-fields-table-wrap table-scroll">
      <table className="data-table run-fields-table">
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Expected</th>
            <th scope="col">Extracted</th>
            <th scope="col">Status</th>
            <th scope="col" className="run-fields-pdf-col">
              PDF
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <RunFieldTableRows
              key={row.field}
              row={row}
              activeHighlightId={activeHighlightId}
              onJumpToHighlight={onJumpToHighlight}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

type RowProps = {
  row: RunFieldRow;
  activeHighlightId: string | null;
  onJumpToHighlight: (highlightId: string) => void;
};

function RunFieldTableRows({ row, activeHighlightId, onJumpToHighlight }: RowProps) {
  const statusClass = `run-field-status run-field-status--${row.status}`;
  const hasPdf = row.highlightIds.length > 0;

  if (row.status === "ambiguous" && row.candidates.length > 1) {
    return (
      <>
        {row.candidates.map((cand, idx) => {
          const active = cand.highlightId != null && activeHighlightId === cand.highlightId;
          return (
            <tr
              key={`${row.field}-${idx}`}
              className={`run-field-row run-field-row--ambiguous run-field-row--clickable ${active ? "run-field-row--active" : ""}`}
              onClick={() => cand.highlightId && onJumpToHighlight(cand.highlightId)}
              onKeyDown={(e) => {
                if ((e.key === "Enter" || e.key === " ") && cand.highlightId) {
                  e.preventDefault();
                  onJumpToHighlight(cand.highlightId);
                }
              }}
              tabIndex={cand.highlightId ? 0 : undefined}
              role={cand.highlightId ? "button" : undefined}
            >
              <td>
                {idx === 0 ? (
                  <span className="run-field-name">{formatFieldLabel(row.field)}</span>
                ) : (
                  <span className="run-field-alt muted small">alternate reading</span>
                )}
              </td>
              <td className="muted small run-field-expected" title={idx === 0 ? row.expectedSummary : undefined}>
                {idx === 0 ? row.expectedSummary : "—"}
              </td>
              <td>
                <strong>{cand.valueLabel}</strong>
                {cand.evidenceText ? (
                  <span className="run-field-evidence-quote muted small"> “{cand.evidenceText}”</span>
                ) : null}
              </td>
              <td>
                {idx === 0 ? <span className={statusClass}>{row.statusLabel}</span> : null}
              </td>
              <td className="run-fields-pdf-col">
                {cand.highlightId ? (
                  <span className="run-field-pdf-link">View →</span>
                ) : (
                  <span className="muted small">—</span>
                )}
              </td>
            </tr>
          );
        })}
      </>
    );
  }

  const primaryId = row.highlightIds[0] ?? null;
  const active = primaryId != null && activeHighlightId === primaryId;

  return (
    <tr
      className={`run-field-row ${hasPdf ? "run-field-row--clickable" : ""} ${active ? "run-field-row--active" : ""}`}
      onClick={() => primaryId && onJumpToHighlight(primaryId)}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && primaryId) {
          e.preventDefault();
          onJumpToHighlight(primaryId);
        }
      }}
      tabIndex={hasPdf ? 0 : undefined}
      role={hasPdf ? "button" : undefined}
    >
      <td>
        <span className="run-field-name">{formatFieldLabel(row.field)}</span>
      </td>
      <td className="muted small run-field-expected" title={row.expectedSummary}>
        {row.expectedSummary}
      </td>
      <td>
        <strong>{row.extractedSummary}</strong>
      </td>
      <td>
        <span className={statusClass}>{row.statusLabel}</span>
      </td>
      <td className="run-fields-pdf-col">
        {hasPdf ? (
          <span className="run-field-pdf-link">View →</span>
        ) : (
          <span className="muted small">No location</span>
        )}
      </td>
    </tr>
  );
}
