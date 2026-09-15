/**
 * Simple mode — vertical scroll with collapsible section cards (Proposal C).
 */

import { useState } from "react";

import { SCHEMA_UI } from "../../lib/schemaUiLabels";
import SchemaVisualEditor from "./SchemaVisualEditor";

export type SchemaSimpleCardsEditorProps = {
  projectId: string;
  body: Record<string, unknown>;
  disabled?: boolean;
  onBodyChange: (body: Record<string, unknown>) => void;
  onError?: (message: string) => void;
};

type SectionId = "strict" | "open" | "cross" | "groups" | "settings";

export default function SchemaSimpleCardsEditor({
  projectId,
  body,
  disabled,
  onBodyChange,
  onError,
}: SchemaSimpleCardsEditorProps) {
  const [openSections, setOpenSections] = useState<Set<SectionId>>(
    () => new Set<SectionId>(["strict", "settings"]),
  );

  function toggle(id: SectionId) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const sections: { id: SectionId; title: string; lead: string }[] = [
    { id: "strict", title: SCHEMA_UI.sectionStrict, lead: SCHEMA_UI.sectionStrictLead },
    { id: "open", title: SCHEMA_UI.sectionOpenEnded, lead: SCHEMA_UI.sectionOpenEndedLead },
    { id: "cross", title: SCHEMA_UI.sectionCross, lead: SCHEMA_UI.sectionCrossLead },
    { id: "groups", title: SCHEMA_UI.sectionGroups, lead: SCHEMA_UI.sectionGroupsLead },
    { id: "settings", title: SCHEMA_UI.sectionPdf, lead: SCHEMA_UI.sectionPdfLead },
  ];

  return (
    <div className="schema-simple-editor">
      <p className="muted small schema-simple-intro">
        Simple layout — expand each card to edit. Switch to <strong>Workspace</strong> to focus one field at a
        time.
      </p>
      {sections.map((sec) => {
        const isOpen = openSections.has(sec.id);
        return (
          <section key={sec.id} className={`schema-simple-card${isOpen ? " schema-simple-card--open" : ""}`}>
            <button type="button" className="schema-simple-card-head" onClick={() => toggle(sec.id)}>
              <span className="schema-simple-card-title">{sec.title}</span>
              <span className="schema-simple-card-chevron" aria-hidden>
                {isOpen ? "−" : "+"}
              </span>
            </button>
            {isOpen ? (
              <div className="schema-simple-card-body">
                <p className="muted small">{sec.lead}</p>
                <SchemaVisualEditor
                  projectId={projectId}
                  body={body}
                  disabled={disabled}
                  onBodyChange={onBodyChange}
                  onError={onError}
                  initialTab={
                    sec.id === "strict"
                      ? "strict"
                      : sec.id === "open"
                        ? "prompt"
                        : sec.id === "cross"
                          ? "cross"
                          : sec.id === "groups"
                            ? "groups"
                            : "settings"
                  }
                  singleTab
                />
              </div>
            ) : (
              <p className="schema-simple-card-collapsed muted small">{sec.lead}</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
