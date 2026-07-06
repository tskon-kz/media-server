import { useState } from "react";
import { Activity, Inbox, Plus, Settings2, type LucideProps } from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { ToastProvider } from "./components/Toast";
import { TorrentList } from "./screens/TorrentList";
import { AddTorrent } from "./screens/AddTorrent";
import { Status } from "./screens/Status";
import { Settings } from "./screens/Settings";
import styles from "./App.module.scss";

type Tab = "list" | "add" | "status" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("list");
  const { t } = useTranslation();

  const TABS: { key: Tab; Icon: ComponentType<LucideProps>; label: string }[] = [
    { key: "list",     Icon: Inbox,     label: t("tabs.torrents") },
    { key: "add",      Icon: Plus,      label: t("tabs.add") },
    { key: "status",   Icon: Activity,  label: t("tabs.status") },
    { key: "settings", Icon: Settings2, label: t("tabs.settings") },
  ];

  return (
    <ToastProvider>
      <div className={styles.content}>
        {tab === "list"     && <TorrentList />}
        {tab === "add"      && <AddTorrent onAdded={() => setTab("list")} />}
        {tab === "status"   && <Status />}
        {tab === "settings" && <Settings />}
      </div>

      <nav className={styles.tabbar}>
        {TABS.map(({ key, Icon, label }) => (
          <button
            key={key}
            className={`${styles.tabItem} ${tab === key ? styles.tabItemActive : ""}`}
            onClick={() => setTab(key)}
          >
            <Icon size={24} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </ToastProvider>
  );
}
