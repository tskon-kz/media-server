import { createContext, useCallback, useContext, type ReactNode } from "react"
import { notifications } from "@mantine/notifications"
import { haptic } from "../telegram"

const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {})

export function useToast() {
  return useContext(ToastCtx)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const show = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    haptic(kind === "err" ? "error" : "success")
    notifications.show({
      message: text,
      color: kind === "err" ? "red" : "tgBlue",
      autoClose: 3000,
      withBorder: true,
      withCloseButton: true,
    })
  }, [])

  return <ToastCtx.Provider value={show}>{children}</ToastCtx.Provider>
}
