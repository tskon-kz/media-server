import {notifications} from "@mantine/notifications"
import {haptic} from "../telegram"

const HAPTIC = {ok: "success", err: "error", warn: "warning"} as const
const COLOR = {ok: "tgBlue", err: "red", warn: "yellow"} as const

export function toast(text: string, kind: "ok" | "err" | "warn" = "ok") {
  haptic(HAPTIC[kind])
  notifications.show({
    message: text,
    color: COLOR[kind],
    autoClose: 3000,
    withBorder: true,
    withCloseButton: true,
  })
}
