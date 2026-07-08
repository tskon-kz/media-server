import { initData } from "./telegram";
import type {
  AppConfig, Category, JellyfinUser, SearchResult, Settings, Torrent, UpdateInfo,
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

  search: (q: string, page = 1, pageSize = 5) =>
    req<{ query: string; results: SearchResult[]; total: number; page: number; page_size: number }>(
      "GET", `/api/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`
    ),
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
