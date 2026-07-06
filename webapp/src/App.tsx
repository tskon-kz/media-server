import { useState } from "react";
import { Tabbar } from "@telegram-apps/telegram-ui";
import { Activity, Inbox, Plus, Search, Settings2, type LucideProps } from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { ToastProvider } from "./components/Toast";
import { TorrentList } from "./screens/TorrentList";
import { AddTorrent } from "./screens/AddTorrent";
import { Search as SearchScreen } from "./screens/Search";
import { Status } from "./screens/Status";
import { Settings } from "./screens/Settings";
import s from "./App.module.scss";

type Tab = "list" | "add" | "search" | "status" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("list");
  const { t } = useTranslation();

  const TABS: { key: Tab; Icon: ComponentType<LucideProps>; label: string }[] = [
    { key: "list",     Icon: Inbox,     label: t("tabs.torrents") },
    { key: "add",      Icon: Plus,      label: t("tabs.add") },
    { key: "search",   Icon: Search,    label: t("tabs.search") },
    { key: "status",   Icon: Activity,  label: t("tabs.status") },
    { key: "settings", Icon: Settings2, label: t("tabs.settings") },
  ];

  return (
    <ToastProvider>
      <div className={s.content}>
        {tab === "list"     && <TorrentList />}
        {tab === "add"      && <AddTorrent onAdded={() => setTab("list")} />}
        {tab === "search"   && <SearchScreen />}
        {tab === "status"   && <Status />}
        {tab === "settings" && <Settings />}
      </div>
      <Tabbar>
        {TABS.map(({ key, Icon, label }) => (
          <Tabbar.Item
            key={key}
            text={label}
            selected={tab === key}
            onClick={() => setTab(key)}
          >
            <Icon size={28} />
          </Tabbar.Item>
        ))}
      </Tabbar>
    </ToastProvider>
  );
}
