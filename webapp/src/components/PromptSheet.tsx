import { useEffect, useState } from "react";
import { Button, Input, Modal } from "@telegram-apps/telegram-ui";

export function PromptSheet({
  title, label, placeholder, password, submitText, open, onSubmit, onClose,
}: {
  title: string;
  label?: string;
  placeholder?: string;
  password?: boolean;
  submitText?: string;
  open: boolean;
  onSubmit: (value: string) => void;
  onClose: () => void;
}) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (!open) setValue("");
  }, [open]);

  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} header={<Modal.Header>{title}</Modal.Header>}>
      <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
        <Input
          header={label}
          type={password ? "password" : "text"}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && value.trim() && onSubmit(value.trim())}
        />
        <Button stretched disabled={!value.trim()} onClick={() => onSubmit(value.trim())}>
          {submitText ?? "Save"}
        </Button>
        <Button stretched mode="bezeled" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </Modal>
  );
}
