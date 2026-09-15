/**
 * Guided 4-step wizard for new schemas (Proposal A).
 */

import { useState } from "react";

import { FIELD_TYPE_OPTIONS } from "../../lib/schemaHelp";
import { formatSchemaKey } from "../../lib/displayLabels";
import { SCHEMA_UI } from "../../lib/schemaUiLabels";
import {
  addStrictField,
  getExtractionSettings,
  getFieldsMap,
  removeStrictField,
  renameStrictField,
  setExtractionSettings,
  textToAliases,
  updateStrictField,
} from "../../lib/schemaModel";
import {
  bodyForWizardDocType,
  WIZARD_DOC_TYPES,
  type WizardDocType,
} from "../../lib/schemaWizardTemplates";
import SchemaDryRunPanel from "./SchemaDryRunPanel";

const STEPS = [
  SCHEMA_UI.wizardStep1,
  SCHEMA_UI.wizardStep2,
  SCHEMA_UI.wizardStep3,
  SCHEMA_UI.wizardStep4,
] as const;

export type SchemaWizardProps = {
  projectId: string;
  schemaKey: string;
  onSchemaKeyChange: (key: string) => void;
  body: Record<string, unknown>;
  onBodyChange: (body: Record<string, unknown>) => void;
  jsonText: string;
  jsonInvalid: boolean;
  disabled?: boolean;
  onComplete: () => void;
};

export default function SchemaWizard({
  projectId,
  schemaKey,
  onSchemaKeyChange,
  body,
  onBodyChange,
  jsonText,
  jsonInvalid,
  disabled,
  onComplete,
}: SchemaWizardProps) {
  const [step, setStep] = useState(0);
  const [docType, setDocType] = useState<WizardDocType>("custom");
  const fields = getFieldsMap(body);
  const extraction = getExtractionSettings(body);

  function patch(fn: (b: Record<string, unknown>) => Record<string, unknown>) {
    onBodyChange(fn(body));
  }

  function pickDocType(id: WizardDocType) {
    setDocType(id);
    const tpl = WIZARD_DOC_TYPES.find((t) => t.id === id);
    if (tpl) onSchemaKeyChange(tpl.suggestedKey);
    onBodyChange(bodyForWizardDocType(id));
  }

  return (
    <div className="schema-wizard">
      <ol className="schema-wizard-steps" aria-label="Wizard progress">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={`schema-wizard-step${i === step ? " schema-wizard-step--active" : ""}${i < step ? " schema-wizard-step--done" : ""}`}
          >
            <span className="schema-wizard-step-num">{i + 1}</span>
            <span className="schema-wizard-step-label">{label}</span>
          </li>
        ))}
      </ol>

      {step === 0 ? (
        <div className="schema-wizard-panel">
          <h3 className="schema-wizard-title">What kind of document are you validating?</h3>
          <p className="muted small">Pick a template — you can refine everything later in the workspace.</p>
          <div className="schema-wizard-tiles">
            {WIZARD_DOC_TYPES.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`schema-wizard-tile${docType === t.id ? " schema-wizard-tile--active" : ""}`}
                disabled={disabled}
                onClick={() => pickDocType(t.id)}
              >
                <span className="schema-wizard-tile-icon" aria-hidden>
                  {t.icon}
                </span>
                <span className="schema-wizard-tile-title">{t.title}</span>
                <span className="muted small">{t.description}</span>
              </button>
            ))}
          </div>
          <label className="field-label schema-wizard-key">
            <span>Checklist ID</span>
            <input
              value={schemaKey}
              onChange={(e) => onSchemaKeyChange(e.target.value)}
              placeholder="supplier_coa"
              spellCheck={false}
              disabled={disabled}
            />
            <span className="muted small">Short name for this rule set (letters, numbers, underscores).</span>
            {schemaKey.trim() ? (
              <p className="schema-wizard-key-preview">
                Shows as <strong>{formatSchemaKey(schemaKey)}</strong>
              </p>
            ) : null}
          </label>
        </div>
      ) : null}

      {step === 1 ? (
        <div className="schema-wizard-panel">
          <h3 className="schema-wizard-title">{SCHEMA_UI.sectionStrict}</h3>
          <p className="muted small">{SCHEMA_UI.sectionStrictLead}</p>
          <div className="schema-wizard-field-list">
            {Object.entries(fields).map(([name, spec]) => (
              <div key={name} className="schema-wizard-field-row">
                <input
                  className="schema-wizard-field-name"
                  value={name}
                  disabled={disabled}
                  spellCheck={false}
                  onChange={(e) => {
                    const nn = e.target.value.trim();
                    if (nn && nn !== name) patch((b) => renameStrictField(b, name, nn));
                  }}
                />
                <select
                  value={spec.type || "string"}
                  disabled={disabled}
                  onChange={(e) => patch((b) => updateStrictField(b, name, { type: e.target.value }))}
                >
                  {FIELD_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <label className="schema-checkbox-label">
                  <input
                    type="checkbox"
                    checked={Boolean(spec.required)}
                    disabled={disabled}
                    onChange={(e) => patch((b) => updateStrictField(b, name, { required: e.target.checked }))}
                  />
                  Required
                </label>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  disabled={disabled}
                  onClick={() => patch((b) => removeStrictField(b, name))}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="btn-secondary btn-sm"
            disabled={disabled}
            onClick={() => patch((b) => addStrictField(b, `field_${Object.keys(fields).length + 1}`))}
          >
            + Add field
          </button>
          <details className="schema-wizard-advanced">
            <summary className="muted small">PDF labels per field (optional)</summary>
            {Object.entries(fields).map(([name, spec]) => (
              <label key={name} className="field-label">
                <span>
                  Labels for <code>{name}</code>
                </span>
                <textarea
                  rows={2}
                  disabled={disabled}
                  value={(spec.aliases ?? []).join("\n")}
                  onChange={(e) =>
                    patch((b) => updateStrictField(b, name, { aliases: textToAliases(e.target.value) }))
                  }
                />
              </label>
            ))}
          </details>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="schema-wizard-panel">
          <h3 className="schema-wizard-title">{SCHEMA_UI.sectionPdf}</h3>
          <p className="muted small">{SCHEMA_UI.sectionPdfLead}</p>
          <label className="field-label schema-checkbox-label">
            <input
              type="checkbox"
              checked={extraction.understand_document !== false}
              disabled={disabled}
              onChange={(e) =>
                patch((b) =>
                  setExtractionSettings(b, { ...getExtractionSettings(b), understand_document: e.target.checked }),
                )
              }
            />
            <span>Understand document layout (recommended)</span>
          </label>
          <label className="field-label schema-checkbox-label">
            <input
              type="checkbox"
              checked={extraction.read_images === true}
              disabled={disabled}
              onChange={(e) =>
                patch((b) =>
                  setExtractionSettings(b, { ...getExtractionSettings(b), read_images: e.target.checked }),
                )
              }
            />
            <span>Read embedded images</span>
          </label>
          <p className="muted small" style={{ marginTop: "1rem" }}>
            Cross-field rules, repeating tables, and extra insights can be added in the workspace after the
            wizard.
          </p>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="schema-wizard-panel">
          <h3 className="schema-wizard-title">Test your schema</h3>
          <p className="muted small">Upload a sample PDF. This does not save a validation run.</p>
          <SchemaDryRunPanel
            projectId={projectId}
            jsonText={jsonText}
            jsonInvalid={jsonInvalid}
            disabled={disabled}
          />
        </div>
      ) : null}

      <footer className="schema-wizard-footer">
        <button type="button" className="btn-secondary" disabled={step === 0 || disabled} onClick={() => setStep((s) => s - 1)}>
          Back
        </button>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            className="btn-primary"
            disabled={disabled || (step === 0 && !schemaKey.trim())}
            onClick={() => setStep((s) => s + 1)}
          >
            Continue
          </button>
        ) : (
          <button type="button" className="btn-primary-lg" disabled={disabled} onClick={onComplete}>
            Open workspace
          </button>
        )}
        <button type="button" className="btn-inline link-button schema-wizard-skip" onClick={onComplete}>
          Skip wizard → workspace
        </button>
      </footer>
    </div>
  );
}
