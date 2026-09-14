import { initData } from "./telegram";
import type {
  AppConfig, Category, JellyfinUser, RenameJob, SearchResult, Settings, Torrent, UpdateInfo,
  UpscaleInfo,
  UpscaleResult,
} from "./types";

// All requests carry the Telegram initData in the Authorization header
// (`tma <initData>`), which the backend validates against the bot token. In dev
// the browser has no initData ("") and the backend's WEBAPP_DEV_MODE accepts it.

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `tma ${initData}`,
  };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const resp = await fetch(path, { method, headers, body: payload });
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j?.error) msg = j.error;
    } catch {
      /* keep default */
    }
    throw new Error(msg);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export type SearchEvent =
  | { type: "progress"; pending: string[] }
  | { type: "results"; results: SearchResult[]; failed: string[] }
  | { type: "error"; error: string }
  | { type: "done" };

// EventSource can't send the Authorization header, so SSE is read over fetch.
async function sse(path: string, onEvent: (event: SearchEvent) => void, signal: AbortSignal): Promise<void> {
  const resp = await fetch(path, { headers: { Authorization: `tma ${initData}` }, signal });
  if (!resp.ok || !resp.body) {
    let msg = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j?.error) msg = j.error;
    } catch {
      /* keep default */
    }
    throw new Error(msg);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let type = "";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) type = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (type) onEvent({ ...(data ? JSON.parse(data) : {}), type } as SearchEvent);
      sep = buffer.indexOf("\n\n");
    }
  }
}

export const api = {
  config: () => req<AppConfig>("GET", "/api/config"),

  torrents: () => req<{ torrents: Torrent[]; has_categories: boolean }>("GET", "/api/torrents"),
  addMagnet: (magnet: string, categoryId?: number) =>
    req<{ added: boolean }>("POST", "/api/torrents", { magnet, category_id: categoryId }),
  addTorrentFile: (file: File, categoryId?: number) => {
    const fd = new FormData();
    fd.append("file", file);
    if (categoryId !== undefined) fd.append("category_id", String(categoryId));
    return req<{ added: boolean }>("POST", "/api/torrents", fd);
  },
  deleteTorrent: (hash: string, deleteFiles = true) =>
    req<{ deleted: boolean }>("POST", `/api/torrents/${hash}/delete`, { delete_files: deleteFiles }),
  removeFromClient: (hash: string) =>
    req<{ removed: boolean }>("POST", `/api/torrents/${hash}/remove-from-client`),
  deleteDiskEntry: (diskId: string) =>
    req<{ deleted: boolean }>("POST", "/api/disk/delete", { disk_id: diskId }),
  moveTorrent: (diskId: string, categoryId: number) =>
    req<{ moved: boolean }>("POST", "/api/torrents/category", { disk_id: diskId, category_id: categoryId }),
  structure: (diskId: string, mode: "pretty" | "flat" | "delete") =>
    req<{ mode: string; linked?: number; pending?: number; xdev?: boolean }>(
      "POST", "/api/torrents/structure", { disk_id: diskId, mode },
    ),
  renameJobs: (diskId: string) =>
    req<{ jobs: RenameJob[] }>("GET", `/api/torrents/rename-jobs?disk_id=${encodeURIComponent(diskId)}`),
  renameJobManual: (id: number, text: string) =>
    req<{ ok: boolean; dst: string }>("POST", `/api/rename-jobs/${id}/manual`, { text }),
  renameJobFlat: (id: number) =>
    req<{ ok: boolean }>("POST", `/api/rename-jobs/${id}/flat`),
  renameJobSkip: (id: number) =>
    req<{ ok: boolean }>("POST", `/api/rename-jobs/${id}/skip`),
  upscale: (diskId: string, upscaler: string, compression: string, target: string,
            sel: { start?: number; end?: number; names?: string[] }) =>
    req<{ queued: number; disk_id: string }>(
      "POST", "/api/torrents/upscale",
      { disk_id: diskId, upscaler, compression, target, ...sel },
    ),
  upscaleInfo: (diskId: string) =>
    req<UpscaleInfo>("GET", `/api/torrents/upscale/info?disk_id=${encodeURIComponent(diskId)}`),
  upscaleResults: (diskId: string) =>
    req<{ results: UpscaleResult[] }>("GET", `/api/torrents/upscale/results?disk_id=${encodeURIComponent(diskId)}`),
  cancelUpscale: (diskId: string) =>
    req<{ cancelled: boolean }>("POST", "/api/torrents/upscale/cancel", { disk_id: diskId }),
  setUpscalePaused: (paused: boolean) =>
    req<{ paused: boolean }>("POST", "/api/upscale/pause", { paused }),
  backup: (diskId: string) =>
    req<{ backing_up: boolean }>("POST", "/api/torrents/backup", { disk_id: diskId }),
  restoreBackup: (diskId: string) =>
    req<{ restoring: boolean }>("POST", "/api/torrents/backup/restore", { disk_id: diskId }),
  deleteBackup: (diskId: string) =>
    req<{ deleted: boolean }>("POST", "/api/torrents/backup/delete", { disk_id: diskId }),

  status: () => req<{
    connected: boolean
    jf_connected?: boolean
    dl?: number
    ul?: number
    dl_data?: number
    ul_data?: number
    free_space?: number
    total_space?: number
    torrents_total?: number
    torrents_downloading?: number
    torrents_seeding?: number
    alt_speed_enabled?: boolean
    dl_rate_limit?: number
    up_rate_limit?: number
  }>("GET", "/api/status"),
  toggleAltSpeed: () => req<{ alt_speed_enabled: boolean }>("POST", "/api/qb/toggle_alt_speed"),
  scan: () => req<{ ok: boolean }>("POST", "/api/scan"),

  searchStream: (q: string, onEvent: (event: SearchEvent) => void, signal: AbortSignal) =>
    sse(`/api/search/stream?q=${encodeURIComponent(q)}`, onEvent, signal),
  searchAdd: (result: SearchResult, categoryId?: number) =>
    req<{ added: boolean }>("POST", "/api/search/add", {
      magnet: result.magnet, link: result.link, category_id: categoryId,
    }),

  categories: () => req<{ categories: Category[] }>("GET", "/api/categories"),
  createCategory: (name: string, jfType: string, slug?: string) =>
    req<{ categories: Category[] }>("POST", "/api/categories", { name, jf_type: jfType, slug }),
  renameCategory: (id: number, name: string) =>
    req<{ categories: Category[] }>("PATCH", `/api/categories/${id}`, { name }),
  deleteCategory: (id: number) =>
    req<{ categories: Category[] }>("DELETE", `/api/categories/${id}`),

  settings: () => req<Settings>("GET", "/api/settings"),
  setRenameMode: (mode: "flat" | "pretty") =>
    req<{ rename_mode: string }>("POST", "/api/settings/rename_mode", { mode }),
  setUpscaleTarget: (target: string) =>
    req<{ upscale_target: string }>("POST", "/api/settings/upscale_target", { target }),
  setLanguage: (lang: string) =>
    req<{ lang: string }>("POST", "/api/settings/language", { lang }),
  setQbPassword: (password: string) =>
    req<{ ok: boolean }>("POST", "/api/settings/qb_password", { password }),
  fetchQbTemp: () =>
    req<{ found: boolean; password?: string }>("POST", "/api/settings/qb/fetch_temp"),
  restartQb: () => req<{ ok: boolean }>("POST", "/api/settings/qb/restart"),
  setJackettPassword: (password: string) =>
    req<{ ok: boolean; has_password: boolean }>("POST", "/api/settings/jackett_password", { password }),

  update: () => req<UpdateInfo>("GET", "/api/update"),
  triggerUpdate: (tag: "stable" | "edge") =>
    req<{ started: boolean; tag: string }>("POST", "/api/update", { tag }),

  jellyfinUsers: () => req<{ users: JellyfinUser[] }>("GET", "/api/settings/jellyfin/users"),
  createJellyfinUser: (name: string, password: string) =>
    req<{ created: JellyfinUser }>("POST", "/api/settings/jellyfin/users", { name, password }),
  deleteJellyfinUser: (id: string) =>
    req<{ deleted: boolean }>("DELETE", `/api/settings/jellyfin/users/${id}`),
};
