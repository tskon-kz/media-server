import { notifications } from "@mantine/notifications"
import { haptic } from "../telegram"

export function toast(text: string, kind: "ok" | "err" = "ok") {
  haptic(kind === "err" ? "error" : "success")
  notifications.show({
    message: text,
    color: kind === "err" ? "red" : "tgBlue",
    autoClose: 3000,
    withBorder: true,
    withCloseButton: true,
  })
}
