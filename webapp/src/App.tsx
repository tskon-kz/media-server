import { useState } from "react";
import { ToastProvider } from "./components/Toast";
import { TorrentList } from "./screens/TorrentList";
import { AddTorrent } from "./screens/AddTorrent";
import { Search } from "./screens/Search";
import { Status } from "./screens/Status";
import { Settings } from "./screens/Settings";
import s from "./App.module.scss";

type Tab = "list" | "add" | "search" | "status" | "settings";

const TABS: { key: Tab; icon: string; label: string }[] = [
  { key: "list", icon: "📥", label: "Torrents" },
  { key: "add", icon: "➕", label: "Add" },
  { key: "search", icon: "🔍", label: "Search" },
  { key: "status", icon: "📊", label: "Status" },
  { key: "settings", icon: "⚙️", label: "Settings" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("list");

  return (
    <ToastProvider>
      <div className={s.app}>
        <div className={s.content}>
          {tab === "list" && <TorrentList />}
          {tab === "add" && <AddTorrent onAdded={() => setTab("list")} />}
          {tab === "search" && <Search />}
          {tab === "status" && <Status />}
          {tab === "settings" && <Settings />}
        </div>
        <nav className={s.tabbar}>
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`${s.tabBtn}${tab === t.key ? ` ${s.active}` : ""}`}
              onClick={() => setTab(t.key)}
            >
              <span className={s.tabIco}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
      </div>
    </ToastProvider>
  );
}
