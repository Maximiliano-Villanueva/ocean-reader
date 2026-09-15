/**
 * Collapsible checklist rules summary on a validation run (default collapsed).
 */

import SchemaBodySummaryView from "../schemas/SchemaBodySummary";
import { formatSchemaKey } from "../../lib/displayLabels";
import { summarizeSchemaBody } from "../../lib/schemaSummary";

export type RunSchemaOverviewProps = {
  schemaSnapshot: Record<string, unknown> | null | undefined;
  schemaKey: string;
  versionLabel: string;
};

export default function RunSchemaOverview({
  schemaSnapshot,
  schemaKey,
  versionLabel,
}: RunSchemaOverviewProps) {
  const summary = summarizeSchemaBody(schemaSnapshot ?? undefined);
  const hasSnapshot = schemaSnapshot && Object.keys(schemaSnapshot).length > 0;

  return (
    <details className="run-schema-overview run-schema-overview--collapsible">
      <summary className="run-schema-overview-summary" id="run-schema-heading">
        <span className="section-heading">Rules applied</span>
        <span className="run-schema-overview-meta muted small">
          {formatSchemaKey(schemaKey)} · v{versionLabel}
        </span>
      </summary>
      <div className="run-schema-overview-body">
        <p className="muted small">
          What the checker expected to find in the document.
        </p>
        {hasSnapshot ? (
          <>
            <SchemaBodySummaryView summary={summary} compact />
            <details className="run-schema-technical">
              <summary className="muted small">Technical schema JSON</summary>
              <pre className="schema-json-view" role="region" aria-label="Schema JSON">
                {JSON.stringify(schemaSnapshot, null, 2)}
              </pre>
            </details>
          </>
        ) : (
          <p className="muted small">Schema snapshot not stored on this run (older history).</p>
        )}
      </div>
    </details>
  );
}
