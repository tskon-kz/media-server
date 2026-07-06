import type { ReactNode } from "react";

// A simple bottom sheet used for action menus, pickers, and confirmations.
export function Sheet({
  title, onClose, children,
}: { title?: string; onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "flex-end", zIndex: 40,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--tg-theme-section-bg-color)",
          width: "100%", maxWidth: 640, margin: "0 auto",
          borderTopLeftRadius: 16, borderTopRightRadius: 16,
          padding: 16, paddingBottom: "calc(16px + env(safe-area-inset-bottom))",
        }}
      >
        {title && <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 12 }}>{title}</div>}
        {children}
      </div>
    </div>
  );
}
