/**
 * Multi-tag attribute picker for validation uploads.
 * Supports key-only tags or key + value; suggests existing project tags.
 */

import { useEffect, useMemo, useState } from "react";

import { api, type ValidationAttributeVocabularyOut } from "../../api";

export type RunAttribute = { key: string; value: string | null };

export type ValidationAttributePickerProps = {
  projectId: string;
  value: RunAttribute[];
  onChange: (next: RunAttribute[]) => void;
  disabled?: boolean;
};

function toMap(attrs: RunAttribute[]): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  for (const a of attrs) {
    const k = a.key.trim();
    if (!k) continue;
    out[k] = a.value?.trim() ? a.value.trim() : null;
  }
  return out;
}

export default function ValidationAttributePicker({
  projectId,
  value,
  onChange,
  disabled = false,
}: ValidationAttributePickerProps) {
  const [vocab, setVocab] = useState<ValidationAttributeVocabularyOut | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [valueInput, setValueInput] = useState("");
  const [keyOnly, setKeyOnly] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api.validation
      .attributeVocabulary(projectId)
      .then(setVocab)
      .catch(() => setVocab({ keys: [], values_by_key: {} }));
  }, [projectId]);

  const valueSuggestions = useMemo(() => {
    const k = keyInput.trim();
    if (!k || !vocab) return [];
    return vocab.values_by_key[k] ?? [];
  }, [keyInput, vocab]);

  const keySuggestions = useMemo(() => {
    const needle = keyInput.trim().toLowerCase();
    const keys = vocab?.keys ?? [];
    if (!needle) return keys.slice(0, 8);
    return keys.filter((k) => k.toLowerCase().includes(needle)).slice(0, 8);
  }, [keyInput, vocab]);

  const attrMap = toMap(value);

  function addAttribute() {
    const key = keyInput.trim();
    if (!key) return;
    const next = { ...attrMap, [key]: keyOnly ? null : valueInput.trim() || null };
    onChange(
      Object.entries(next).map(([k, v]) => ({ key: k, value: v })),
    );
    setKeyInput("");
    setValueInput("");
    setKeyOnly(false);
  }

  function removeAttribute(key: string) {
    const next = { ...attrMap };
    delete next[key];
    onChange(Object.entries(next).map(([k, v]) => ({ key: k, value: v })));
  }

  return (
    <div className="validation-attribute-picker" aria-label="Validation tags">
      <div className="validation-attribute-picker-head">
        <span className="field-label-text">Tags</span>
        <span className="muted small">Optional — group runs for Insights (e.g. batch, vendor, region)</span>
      </div>

      {value.length > 0 ? (
        <ul className="validation-attribute-chips" role="list">
          {value.map((a) => (
            <li key={a.key} className="validation-attribute-chip" role="listitem">
              <span className="validation-attribute-chip-key">{a.key}</span>
              {a.value ? (
                <>
                  <span className="validation-attribute-chip-sep" aria-hidden>:</span>
                  <span className="validation-attribute-chip-value">{a.value}</span>
                </>
              ) : (
                <span className="validation-attribute-chip-flag muted small">(flag)</span>
              )}
              <button
                type="button"
                className="validation-attribute-chip-remove"
                aria-label={`Remove tag ${a.key}`}
                disabled={disabled}
                onClick={() => removeAttribute(a.key)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small validation-attribute-empty">No tags yet — add one below or pick a suggestion.</p>
      )}

      <div className="validation-attribute-add-row">
        <label className="field-label validation-attribute-field">
          <span className="sr-only">Tag key</span>
          <input
            type="text"
            list="validation-attribute-key-suggestions"
            placeholder="Key (e.g. batch)"
            value={keyInput}
            disabled={disabled}
            onChange={(e) => setKeyInput(e.target.value)}
          />
          <datalist id="validation-attribute-key-suggestions">
            {keySuggestions.map((k) => (
              <option key={k} value={k} />
            ))}
          </datalist>
        </label>
        <label className="field-label validation-attribute-field">
          <span className="sr-only">Tag value</span>
          <input
            type="text"
            list="validation-attribute-value-suggestions"
            placeholder={keyOnly ? "Key-only tag" : "Value (optional)"}
            value={valueInput}
            disabled={disabled || keyOnly}
            onChange={(e) => setValueInput(e.target.value)}
          />
          <datalist id="validation-attribute-value-suggestions">
            {valueSuggestions.map((v) => (
              <option key={v} value={v} />
            ))}
          </datalist>
        </label>
        <label className="validation-attribute-keyonly">
          <input
            type="checkbox"
            checked={keyOnly}
            disabled={disabled}
            onChange={(e) => setKeyOnly(e.target.checked)}
          />
          <span className="small">Key only</span>
        </label>
        <button type="button" className="btn-secondary" disabled={disabled || !keyInput.trim()} onClick={addAttribute}>
          Add tag
        </button>
      </div>
    </div>
  );
}
