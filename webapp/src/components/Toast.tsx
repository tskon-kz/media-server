import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { Snackbar } from "@telegram-apps/telegram-ui";
import { haptic } from "../telegram";

type ToastEntry = { id: number; text: string };
const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastEntry | null>(null);

  const show = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    haptic(kind === "err" ? "error" : "success");
    setToast({ id: Date.now(), text });
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && (
        <Snackbar key={toast.id} onClose={() => setToast(null)} duration={2600}>
          {toast.text}
        </Snackbar>
      )}
    </ToastCtx.Provider>
  );
}
