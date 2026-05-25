/**
 * Version history table for one schema key with readable actions and definition preview.
 */

import { useState } from "react";

import type { ValidationSchemaVersionDetailOut, ValidationSchemaVersionSummary } from "../../api";
import { formatSchemaTimestamp, summarizeSchemaBody } from "../../lib/schemaSummary";
import SchemaBodySummaryView from "./SchemaBodySummary";
import SchemaStatusPill from "./SchemaStatusPill";

export type SchemaVersionTableProps = {
  schemaKey: string;
  versions: ValidationSchemaVersionSummary[];
  expandedId: string | null;
  detailById: Record<string, ValidationSchemaVersionDetailOut>;
  detailLoading: string | null;
  busy: boolean;
  onToggleDefinition: (rowId: string) => void;
  onForkRevision: (v: ValidationSchemaVersionSummary) => void;
  onDelete: (rowId: string, label: string) => void;
};

export default function SchemaVersionTable({
  schemaKey,
  versions,
  expandedId,
  detailById,
  detailLoading,
  busy,
  onToggleDefinition,
  onForkRevision,
  onDelete,
}: SchemaVersionTableProps) {
  const active = versions.find((v) => v.status.toLowerCase() === "active");

  return (
    <div className="schema-version-table-wrap">
      {active ? (
        <p className="schema-active-hint muted small">
          Active revision: <strong>{active.version_label}</strong> — used for new validation runs unless you pick
          another version on the run page.
        </p>
      ) : null}
      <div className="table-scroll">
        <table className="data-table schema-versions-table">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Status</th>
              <th scope="col">Created</th>
              <th scope="col" className="schema-versions-actions-col">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <SchemaVersionRow
                key={v.id}
                schemaKey={schemaKey}
                version={v}
                expanded={expandedId === v.id}
                detail={detailById[v.id]}
                loading={detailLoading === v.id}
                busy={busy}
                onToggle={() => onToggleDefinition(v.id)}
                onFork={() => onForkRevision(v)}
                onDelete={() => onDelete(v.id, `${schemaKey}@${v.version_label}`)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type RowProps = {
  schemaKey: string;
  version: ValidationSchemaVersionSummary;
  expanded: boolean;
  detail?: ValidationSchemaVersionDetailOut;
  loading: boolean;
  busy: boolean;
  onToggle: () => void;
  onFork: () => void;
  onDelete: () => void;
};

function SchemaVersionRow({
  version,
  expanded,
  detail,
  loading,
  busy,
  onToggle,
  onFork,
  onDelete,
}: RowProps) {
  const [showRawJson, setShowRawJson] = useState(false);
  const summary = detail ? summarizeSchemaBody(detail.body as Record<string, unknown>) : null;

  return (
    <>
      <tr className={expanded ? "schema-version-row--expanded" : undefined}>
        <td>
          <strong>{version.version_label}</strong>
        </td>
        <td>
          <SchemaStatusPill status={version.status} />
        </td>
        <td className="muted small">{formatSchemaTimestamp(version.created_at)}</td>
        <td>
          <div className="schema-version-actions">
            <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={onToggle}>
              {expanded ? "Hide" : "View"} rules
            </button>
            <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={onFork}>
              New revision from this
            </button>
            <button type="button" className="danger btn-sm" disabled={busy} onClick={onDelete}>
              Delete
            </button>
          </div>
        </td>
      </tr>
      {expanded ? (
        <tr className="schema-version-detail-row">
          <td colSpan={4}>
            {loading ? (
              <p className="muted small">Loading definition…</p>
            ) : detail && summary ? (
              <div className="schema-version-detail-panel">
                <div className="schema-version-detail-toolbar row">
                  <button
                    type="button"
                    className="btn-inline link-button"
                    onClick={() => setShowRawJson((x) => !x)}
                  >
                    {showRawJson ? "Show summary" : "Show raw JSON"}
                  </button>
                </div>
                {showRawJson ? (
                  <pre className="schema-json-view">{JSON.stringify(detail.body, null, 2)}</pre>
                ) : (
                  <SchemaBodySummaryView summary={summary} />
                )}
              </div>
            ) : (
              <p className="muted small">Definition not loaded.</p>
            )}
          </td>
        </tr>
      ) : null}
    </>
  );
}
