export interface Torrent {
  disk_id: string;
  hash: string | null;
  in_qbittorrent: boolean;
  name: string;
  raw_name: string;
  state: string;
  icon: string;
  progress: number;
  size: number | null;
  dlspeed: number;
  upspeed: number;
  eta: number;
  save_path: string;
  renameable: boolean;
}

export interface Category {
  id: number;
  name: string;
  path: string;
  jf_type: string;
}

export interface SearchResult {
  title: string;
  seeders: number;
  size: number;
  tracker: string;
  date: string;
  details: string;
  magnet: string | null;
  link: string | null;
}

export interface QuickLinks {
  qbittorrent: string;
  jellyfin: string;
  jackett: string;
}

export interface AppConfig {
  version: string;
  lang: string;
  rename_mode: "flat" | "pretty";
  webapp_url: string;
  quick_links: QuickLinks | null;
  has_categories: boolean;
}

export interface Settings {
  rename_mode: "flat" | "pretty";
  lang: string;
  qbittorrent: { user: string; is_perm: boolean; status: string };
  jackett: { has_key: boolean; has_password: boolean };
  jellyfin: { has_key: boolean };
}

export interface JellyfinUser {
  id: string;
  name: string;
}

export interface UpdateInfo {
  current: string;
  latest: string | null;
  has_update: boolean;
  channel: "stable" | "edge";
}
