import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { haptic } from "../telegram";

type Toast = { id: number; text: string };
const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    haptic(kind === "err" ? "error" : "success");
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2600);
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toasts.map((t) => (
        <div key={t.id} className="toast">{t.text}</div>
      ))}
    </ToastCtx.Provider>
  );
}
