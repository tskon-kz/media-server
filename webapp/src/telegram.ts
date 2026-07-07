// Thin, typed wrapper over Telegram's official telegram-web-app.js global.
// Using the CDN script (loaded in index.html) instead of an npm SDK keeps the
// app free of SDK version churn — the global is the stable, documented surface.
// Every call degrades gracefully when running outside Telegram (Vite dev in a
// plain browser), so the same code path works in dev and prod.

interface TgButton {
  setText(t: string): TgButton;
  show(): TgButton;
  hide(): TgButton;
  enable(): TgButton;
  disable(): TgButton;
  showProgress(leaveActive?: boolean): TgButton;
  hideProgress(): TgButton;
  onClick(cb: () => void): TgButton;
  offClick(cb: () => void): TgButton;
  isVisible: boolean;
}

interface TgWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  isExpanded: boolean;
  ready(): void;
  expand(): void;
  openLink(url: string, opts?: { try_instant_view?: boolean }): void;
  onEvent(event: string, cb: () => void): void;
  offEvent(event: string, cb: () => void): void;
  MainButton: TgButton;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback?: { impactOccurred(style: string): void; notificationOccurred(type: string): void };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export const tg: TgWebApp | undefined = window.Telegram?.WebApp;

/** The signed initData string, or "" in a plain browser (backend dev-mode auth). */
export const initData = tg?.initData ?? "";

export function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
}

export function openExternal(url: string) {
  if (tg) tg.openLink(url);
  else window.open(url, "_blank", "noopener");
}

export function haptic(kind: "light" | "medium" | "heavy" | "success" | "error" = "light") {
  const h = tg?.HapticFeedback;
  if (!h) return;
  if (kind === "success" || kind === "error") h.notificationOccurred(kind);
  else h.impactOccurred(kind);
}

/** Back button: show while `active`, wire to `cb`. Returns a cleanup fn. */
export function useBackButton() {
  return {
    show(cb: () => void) {
      if (!tg) return () => {};
      tg.BackButton.show();
      tg.BackButton.onClick(cb);
      return () => {
        tg.BackButton.offClick(cb);
        tg.BackButton.hide();
      };
    },
  };
}

export const mainButton = {
  set(text: string, cb: () => void) {
    if (!tg) return () => {};
    const b = tg.MainButton;
    b.setText(text).show().enable();
    b.onClick(cb);
    return () => {
      b.offClick(cb);
      b.hide();
    };
  },
  progress(on: boolean) {
    if (!tg) return;
    if (on) tg.MainButton.showProgress();
    else tg.MainButton.hideProgress();
  },
};
