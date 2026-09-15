/**
 * Conversational schema authoring (ADK agent via backend proxy).
 */

import { useRef, useState } from "react";

import { api } from "../../api";
import type { SchemaValidationFeedback } from "../../lib/schemaModel";

export type SchemaAgentPanelProps = {
  projectId: string;
  schemaBody: Record<string, unknown>;
  onSchemaBodyChange: (body: Record<string, unknown>) => void;
  validationFeedback?: SchemaValidationFeedback | null;
  disabled?: boolean;
  /** ``studio`` = left rail in Schema Studio; ``chat-only`` = legacy compact layout. */
  layout?: "split" | "chat-only" | "studio";
};

type ChatLine = { role: "user" | "assistant"; content: string };

export default function SchemaAgentPanel({
  projectId,
  schemaBody,
  onSchemaBodyChange,
  validationFeedback = null,
  disabled = false,
  layout = "split",
}: SchemaAgentPanelProps) {
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sampleNote, setSampleNote] = useState("");
  const [sampleFileName, setSampleFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const isStudio = layout === "studio";

  async function send() {
    const text = input.trim();
    if (!text || busy || disabled) return;
    setBusy(true);
    setError(null);
    const nextLines: ChatLine[] = [...lines, { role: "user", content: text }];
    setLines(nextLines);
    setInput("");
    try {
      const out = await api.validation.schemaAgentChat(projectId, {
        messages: nextLines,
        schema_body: schemaBody,
        sample_pdf_note: sampleNote.trim() || null,
        validation_feedback: validationFeedback ?? undefined,
      });
      setLines((prev) => [...prev, { role: "assistant", content: out.reply }]);
      onSchemaBodyChange(out.schema_body);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSamplePdf(file: File | null) {
    if (!file || !projectId) return;
    setBusy(true);
    setError(null);
    try {
      const preview = await api.validation.schemaAgentSamplePdf(projectId, file);
      setSampleNote(preview.text_preview);
      setSampleFileName(file.name);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const panelClass = [
    "schema-agent-panel",
    isStudio ? "schema-agent-panel--studio" : "",
    layout === "chat-only" ? "schema-agent-panel--chat-only" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const messagesClass = isStudio ? "schema-agent-messages schema-agent-messages--studio" : "schema-agent-messages";
  const composeClass = isStudio ? "schema-agent-compose schema-agent-compose--studio" : "schema-agent-compose";

  return (
    <div className={panelClass}>
      <h3 className="schema-agent-heading">Assistant</h3>
      <p className={isStudio ? "schema-agent-sub" : "muted small"}>
        Describe fields, ranges, cross-field logic, or open-ended checks in plain language.
      </p>
      <div className="schema-agent-sample-row">
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={(e) => void onSamplePdf(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className="btn-secondary btn-sm"
          disabled={disabled || busy}
          onClick={() => fileRef.current?.click()}
        >
          Attach sample PDF
        </button>
        {sampleFileName ? (
          <span className="muted small" style={{ display: "block", marginTop: "0.35rem" }}>
            {sampleFileName}
          </span>
        ) : null}
      </div>
      <div className={messagesClass} role="log" aria-live="polite">
        {lines.length === 0 ? (
          <p className="muted small">
            Example: “Add strict fields for invoice total and date, plus an informative executive summary.”
          </p>
        ) : (
          lines.map((ln, i) => (
            <div key={i} className={`schema-agent-msg schema-agent-msg--${ln.role}`}>
              <span className="schema-agent-msg-role">{ln.role === "user" ? "You" : "Agent"}</span>
              <p>{ln.content}</p>
            </div>
          ))
        )}
      </div>
      {error ? (
        <p className="alert-error small" role="alert" style={{ padding: "0 1rem" }}>
          {error}
        </p>
      ) : null}
      <div className={composeClass}>
        <textarea
          rows={3}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe what this schema should extract and validate…"
          disabled={disabled || busy}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <button
          type="button"
          className="btn-primary"
          disabled={disabled || busy || !input.trim()}
          onClick={() => void send()}
        >
          {busy ? "Thinking…" : "Send"}
        </button>
      </div>
    </div>
  );
}
