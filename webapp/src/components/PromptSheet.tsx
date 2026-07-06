import { useState } from "react";
import { Sheet } from "./Sheet";

// A one-field prompt — collapses a bot text-input FSM step into a single dialog.
export function PromptSheet({
  title, label, placeholder, password, submitText, onSubmit, onClose,
}: {
  title: string;
  label?: string;
  placeholder?: string;
  password?: boolean;
  submitText?: string;
  onSubmit: (value: string) => void;
  onClose: () => void;
}) {
  const [value, setValue] = useState("");
  return (
    <Sheet title={title} onClose={onClose}>
      {label && <label>{label}</label>}
      <input
        autoFocus
        type={password ? "password" : "text"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && value.trim() && onSubmit(value.trim())}
      />
      <div className="btn-row">
        <button className="secondary" onClick={onClose}>Cancel</button>
        <button disabled={!value.trim()} onClick={() => onSubmit(value.trim())}>
          {submitText ?? "Save"}
        </button>
      </div>
    </Sheet>
  );
}
