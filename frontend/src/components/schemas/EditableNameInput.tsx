/**
 * Name field that keeps focus while typing; commits rename on blur.
 */

import { useEffect, useState, type ReactNode } from "react";

export type EditableNameInputProps = {
  name: string;
  disabled?: boolean;
  label: ReactNode;
  onRename: (newName: string) => void;
};

export default function EditableNameInput({ name, disabled, label, onRename }: EditableNameInputProps) {
  const [draft, setDraft] = useState(name);

  useEffect(() => {
    setDraft(name);
  }, [name]);

  function commit() {
    const trimmed = draft.trim();
    if (!trimmed) {
      setDraft(name);
      return;
    }
    if (trimmed !== name) {
      onRename(trimmed);
    }
  }

  return (
    <label className="field-label schema-inline-label">
      <span>{label}</span>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => commit()}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.currentTarget.blur();
          }
        }}
        spellCheck={false}
        disabled={disabled}
      />
    </label>
  );
}
