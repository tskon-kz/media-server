import { useCallback, useEffect, useRef } from "react"
import { tg } from "./telegram"
import { useAppDispatch, useAppSelector } from "./store"
import { setMode, setAppearance, type Appearance, type ThemeMode } from "./store/slices/themeSlice"

export type { Appearance, ThemeMode }

function telegramAppearance(): Appearance {
  return (tg?.colorScheme ?? "light") as Appearance
}

function applyToDOM(a: Appearance) {
  document.documentElement.dataset.theme = a
}

export function ThemeSync() {
  const dispatch = useAppDispatch()
  const modeRef = useRef(useAppSelector((s) => s.theme.mode))

  useEffect(() => {
    const a = modeRef.current === "auto" ? telegramAppearance() : modeRef.current
    dispatch(setAppearance(a))
    applyToDOM(a)
  }, [dispatch])

  useEffect(() => {
    const handler = () => {
      if (modeRef.current === "auto") {
        const a = telegramAppearance()
        dispatch(setAppearance(a))
        applyToDOM(a)
      }
    }
    tg?.onEvent("themeChanged", handler)
    return () => tg?.offEvent("themeChanged", handler)
  }, [dispatch])

  return null
}

export function useTheme() {
  const dispatch = useAppDispatch()
  const mode = useAppSelector((s) => s.theme.mode)
  const appearance = useAppSelector((s) => s.theme.appearance)

  const setThemeMode = useCallback(
    (m: ThemeMode) => {
      const a = m === "auto" ? telegramAppearance() : m
      dispatch(setMode({ mode: m, appearance: a }))
      applyToDOM(a)
    },
    [dispatch],
  )

  return { mode, appearance, setMode: setThemeMode }
}
