import { type ReactNode } from "react";
import { Modal } from "@telegram-apps/telegram-ui";

export function Sheet({
  title, open, onClose, children,
}: {
  title?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={(o) => !o && onClose()}
      header={title ? <Modal.Header>{title}</Modal.Header> : undefined}
    >
      <div style={{ padding: "0 16px 16px" }}>
        {children}
      </div>
    </Modal>
  );
}
