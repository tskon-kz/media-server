import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { tg } from "./telegram";

export type Appearance = "light" | "dark";
export type ThemeMode = "auto" | "light" | "dark";

function telegramAppearance(): Appearance {
  return (tg?.colorScheme ?? "light") as Appearance;
}

function applyToDOM(a: Appearance) {
  document.documentElement.dataset.theme = a;
}

interface ThemeCtxValue {
  appearance: Appearance;
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
}

const ThemeCtx = createContext<ThemeCtxValue>({ appearance: "light", mode: "auto", setMode: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const savedMode = localStorage.getItem("theme-mode") as ThemeMode | null;
  const initialMode: ThemeMode = savedMode === "light" || savedMode === "dark" ? savedMode : "auto";
  const initialAppearance: Appearance = initialMode === "auto" ? telegramAppearance() : initialMode;

  const [mode, setModeState] = useState<ThemeMode>(initialMode);
  const [appearance, setAppearance] = useState<Appearance>(initialAppearance);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const setMode = useCallback((m: ThemeMode) => {
    localStorage.setItem("theme-mode", m);
    const a = m === "auto" ? telegramAppearance() : m;
    setModeState(m);
    setAppearance(a);
    applyToDOM(a);
  }, []);

  useEffect(() => {
    applyToDOM(appearance);
  }, [appearance]);

  useEffect(() => {
    const handler = () => {
      if (modeRef.current === "auto") {
        const a = telegramAppearance();
        setAppearance(a);
        applyToDOM(a);
      }
    };
    tg?.onEvent("themeChanged", handler);
    return () => tg?.offEvent("themeChanged", handler);
  }, []);

  return <ThemeCtx.Provider value={{ appearance, mode, setMode }}>{children}</ThemeCtx.Provider>;
}

export function useTheme() {
  return useContext(ThemeCtx);
}
