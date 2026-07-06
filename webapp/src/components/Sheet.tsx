import { type ReactNode } from "react";
import { Drawer } from "@mantine/core";

export function Sheet({
  title, open, onClose, children,
}: {
  title?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Drawer
      opened={open}
      onClose={onClose}
      title={title}
      position="bottom"
      radius="lg"
      overlayProps={{ blur: 2 }}
    >
      <div style={{ padding: "0 4px 16px" }}>
        {children}
      </div>
    </Drawer>
  );
}
