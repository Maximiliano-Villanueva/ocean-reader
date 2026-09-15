/**
 * Two-pane schema authoring: conversation (left) and live schema JSON + summary (right).
 */

import SchemaAgentPanel from "./SchemaAgentPanel";
import SchemaBodySummaryView from "./SchemaBodySummary";
import { summarizeSchemaBody } from "../../lib/schemaSummary";

export type SchemaAuthoringWorkspaceProps = {
  projectId: string;
  jsonText: string;
  onJsonTextChange: (text: string) => void;
  disabled?: boolean;
};

export default function SchemaAuthoringWorkspace({
  projectId,
  jsonText,
  onJsonTextChange,
  disabled = false,
}: SchemaAuthoringWorkspaceProps) {
  let schemaBody: Record<string, unknown> = {};
  let jsonInvalid = false;
  try {
    schemaBody = JSON.parse(jsonText) as Record<string, unknown>;
  } catch {
    jsonInvalid = true;
  }
  const summary = summarizeSchemaBody(schemaBody);

  return (
    <div className="schema-authoring-workspace">
      <div className="schema-authoring-chat-pane">
        <SchemaAgentPanel
          projectId={projectId}
          schemaBody={schemaBody}
          disabled={disabled || jsonInvalid}
          onSchemaBodyChange={(body) => onJsonTextChange(JSON.stringify(body, null, 2))}
          layout="chat-only"
        />
      </div>
      <div className="schema-authoring-schema-pane">
        <h3 className="schema-agent-heading">Schema (you can edit anytime)</h3>
        {jsonInvalid ? (
          <p className="alert-error small">Invalid JSON — fix before publishing.</p>
        ) : (
          <SchemaBodySummaryView summary={summary} compact />
        )}
        <label className="field-label schema-authoring-json-label">
          <span className="muted small">Definition JSON</span>
          <textarea
            className="schema-json-editor"
            rows={16}
            value={jsonText}
            onChange={(e) => onJsonTextChange(e.target.value)}
            spellCheck={false}
            disabled={disabled}
          />
        </label>
      </div>
    </div>
  );
}
