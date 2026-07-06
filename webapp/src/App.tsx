import { useState } from "react";
import { ToastProvider } from "./components/Toast";
import { TorrentList } from "./screens/TorrentList";
import { AddTorrent } from "./screens/AddTorrent";
import { Search } from "./screens/Search";
import { Status } from "./screens/Status";
import { Settings } from "./screens/Settings";

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
      <div className="app">
        <div className="content">
          {tab === "list" && <TorrentList />}
          {tab === "add" && <AddTorrent onAdded={() => setTab("list")} />}
          {tab === "search" && <Search />}
          {tab === "status" && <Status />}
          {tab === "settings" && <Settings />}
        </div>
        <nav className="tabbar">
          {TABS.map((t) => (
            <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
              <span className="tab-ico">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
      </div>
    </ToastProvider>
  );
}
