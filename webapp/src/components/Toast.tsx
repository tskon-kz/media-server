import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { Box, Notification } from "@mantine/core";
import { haptic } from "../telegram";

type ToastEntry = { id: number; text: string; kind: "ok" | "err" };
const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastEntry | null>(null);

  const show = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    haptic(kind === "err" ? "error" : "success");
    setToast({ id: Date.now(), text, kind });
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && (
        <Box
          key={toast.id}
          style={{
            position: "fixed",
            bottom: 90,
            left: 16,
            right: 16,
            zIndex: 1000,
            maxWidth: 480,
            margin: "0 auto",
          }}
        >
          <Notification
            color={toast.kind === "err" ? "red" : "tgBlue"}
            withCloseButton
            onClose={() => setToast(null)}
            withBorder
            style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}
          >
            {toast.text}
          </Notification>
        </Box>
      )}
    </ToastCtx.Provider>
  );
}