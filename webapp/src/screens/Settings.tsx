import { useEffect, useState } from "react";
import {
  Button, Caption, Cell, Input, List, Modal, Section,
  SegmentedControl, Spinner, Switch, Title,
} from "@telegram-apps/telegram-ui";
import {
  Clapperboard, Film, Lock, Music, Package, Plus,
  Trash2, Tv, Unlock, UserPlus, Users,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { openExternal } from "../telegram";
import { useToast } from "../components/Toast";
import { useTheme, type ThemeMode } from "../theme";
import { setAppLanguage } from "../i18n";
import { Collapse } from "../components/Collapse";
import { PromptSheet } from "../components/PromptSheet";
import type { AppConfig, Category, JellyfinUser, Settings as SettingsData } from "../types";

const DEL_COLOR = "var(--tgui--destructive_text_color)";

export function Settings() {
  const toast = useToast();
  const { t } = useTranslation();
  const { mode: themeMode, setMode: setThemeMode } = useTheme();
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [st, setSt] = useState<SettingsData | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [users, setUsers] = useState<JellyfinUser[] | null>(null);
  const [dialog, setDialog] = useState<string | null>(null);
  const [newCatName, setNewCatName] = useState("");
  const [renameCat, setRenameCat] = useState<Category | null>(null);
  const [newUserName, setNewUserName] = useState("");

  const reload = async () => {
    const [c, s, ct] = await Promise.all([api.config(), api.settings(), api.categories()]);
    setCfg(c); setSt(s); setCats(ct.categories);
    setAppLanguage(s.lang);
  };

  useEffect(() => { reload().catch((e) => toast((e as Error).message, "err")); }, []); // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try { await fn(); } catch (e) { toast((e as Error).message, "err"); }
  };

  if (!cfg || !st) return <Spinner size="m" style={{ display: "block", margin: "40px auto" }} />;

  const JF_TYPES: { key: string; label: string; Icon: typeof Clapperboard }[] = [
    { key: "movies",  label: t("settings.movies"),  Icon: Film },
    { key: "tvshows", label: t("settings.tvShows"), Icon: Tv },
    { key: "music",   label: t("settings.music"),   Icon: Music },
    { key: "mixed",   label: t("settings.other"),   Icon: Package },
  ];

  const toggleRename = () => guard(async () => {
    const mode = st.rename_mode === "flat" ? "pretty" : "flat";
    await api.setRenameMode(mode);
    toast(mode === "pretty" ? t("settings.smartOn") : t("settings.originalOn"));
    reload();
  });

  const setLang = (lang: string) => guard(async () => {
    await api.setLanguage(lang);
    setAppLanguage(lang);
    reload();
  });

  const createCat = (type: string) => guard(async () => {
    await api.createCategory(newCatName, type);
    setDialog(null); setNewCatName("");
    toast(t("settings.catAdded"));
    reload();
  });

  const doRenameCat = (name: string) => guard(async () => {
    if (renameCat) await api.renameCategory(renameCat.id, name);
    setRenameCat(null); setDialog(null);
    reload();
  });

  const delCat = (c: Category) => guard(async () => {
    await api.deleteCategory(c.id);
    toast(t("settings.catDeleted"));
    reload();
  });

  const openUsers = () => guard(async () => {
    const u = await api.jellyfinUsers();
    setUsers(u.users);
    setDialog("users");
  });

  const addUser = (password: string) => guard(async () => {
    await api.createJellyfinUser(newUserName, password);
    setDialog("users"); setNewUserName("");
    toast(t("settings.userCreated"));
    const u = await api.jellyfinUsers();
    setUsers(u.users);
  });

  const delUser = (u: JellyfinUser) => guard(async () => {
    await api.deleteJellyfinUser(u.id);
    const list = await api.jellyfinUsers();
    setUsers(list.users);
  });

  const qbPass = (p: string) => guard(async () => {
    await api.setQbPassword(p); setDialog(null); toast(t("settings.qbPassChanged")); reload();
  });
  const qbTemp = () => guard(async () => {
    const r = await api.fetchQbTemp();
    toast(r.found ? t("settings.tempPass", { password: r.password }) : t("settings.noTemp"), r.found ? "ok" : "err");
    reload();
  });
  const qbRestart = () => guard(async () => {
    const r = await api.restartQb();
    toast(r.ok ? t("settings.qbRestarting") : t("settings.restartFailed"), r.ok ? "ok" : "err");
  });
  const jackettPass = (p: string) => guard(async () => {
    await api.setJackettPassword(p); setDialog(null); toast(t("settings.jackettPassUpdated")); reload();
  });
  const jackettRemovePass = () => guard(async () => {
    await api.setJackettPassword(""); toast(t("settings.jackettPassRemoved")); reload();
  });

  return (
    <div>
      <div style={{ padding: "16px 16px 4px" }}>
        <Title>{t("settings.title")}</Title>
      </div>
      <List>
        {/* Auto-structure toggle */}
        <Section>
          <Cell
            subtitle={st.rename_mode === "pretty" ? t("settings.smartSub") : t("settings.originalSub")}
            after={<Switch checked={st.rename_mode === "pretty"} onChange={toggleRename} />}
            multiline
          >
            {t("settings.autoStructure")}
          </Cell>
        </Section>

        {/* Language picker */}
        <Section header={t("settings.language")}>
          <div style={{ padding: "8px 16px 12px" }}>
            <SegmentedControl>
              <SegmentedControl.Item selected={st.lang === "ru"} onClick={() => setLang("ru")}>RU</SegmentedControl.Item>
              <SegmentedControl.Item selected={st.lang === "en"} onClick={() => setLang("en")}>EN</SegmentedControl.Item>
            </SegmentedControl>
          </div>
        </Section>

        {/* Appearance picker */}
        <Section header={t("settings.appearance")}>
          <div style={{ padding: "8px 16px 12px" }}>
            <SegmentedControl>
              <SegmentedControl.Item selected={themeMode === "auto"} onClick={() => setThemeMode("auto" as ThemeMode)}>{t("settings.auto")}</SegmentedControl.Item>
              <SegmentedControl.Item selected={themeMode === "light"} onClick={() => setThemeMode("light" as ThemeMode)}>{t("settings.light")}</SegmentedControl.Item>
              <SegmentedControl.Item selected={themeMode === "dark"} onClick={() => setThemeMode("dark" as ThemeMode)}>{t("settings.dark")}</SegmentedControl.Item>
            </SegmentedControl>
          </div>
        </Section>

        {/* Categories */}
        <Collapse title={t("settings.categories")}>
          <Section>
            {cats.map((c) => (
              <Cell
                key={c.id}
                subtitle={c.path.replace("/media/", "")}
                after={
                  <Button
                    mode="plain"
                    size="s"
                    style={{ color: DEL_COLOR }}
                    onClick={(e) => { e.stopPropagation(); delCat(c); }}
                  >
                    <Trash2 size={18} />
                  </Button>
                }
                onClick={() => { setRenameCat(c); setDialog("renameCat"); }}
                multiline
              >
                {c.name}
              </Cell>
            ))}
          </Section>
          <div style={{ padding: "8px 16px" }}>
            <Button stretched mode="bezeled" before={<Plus size={18} />} onClick={() => setDialog("newCat")}>
              {t("settings.addCategory")}
            </Button>
          </div>
        </Collapse>

        {/* qBittorrent */}
        <Collapse title={t("settings.qb")}>
          <Section>
            <Cell
              subtitle={t("settings.userSub", { user: st.qbittorrent.user })}
              after={st.qbittorrent.is_perm ? <Lock size={16} /> : undefined}
              multiline
            >
              {t("settings.credentials")}
            </Cell>
          </Section>
          <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
            <Button stretched mode="bezeled" onClick={() => setDialog("qbPass")}>{t("settings.changePass")}</Button>
            {!st.qbittorrent.is_perm && <Button stretched mode="bezeled" onClick={qbTemp}>{t("settings.getTemp")}</Button>}
            <Button stretched mode="bezeled" onClick={qbRestart}>{t("settings.restart")}</Button>
          </div>
        </Collapse>

        {/* Jackett */}
        <Collapse title={t("settings.jackett")}>
          <Section>
            <Cell
              subtitle={t("settings.apiKey", { status: t(st.jackett.has_key ? "settings.keyAvailable" : "settings.keyMissing") })}
              after={st.jackett.has_password ? <Lock size={16} /> : <Unlock size={16} />}
              multiline
            >
              {t("settings.jackett")}
            </Cell>
          </Section>
          <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
            <Button stretched mode="bezeled" onClick={() => setDialog("jackettPass")}>{t("settings.changePass")}</Button>
            {st.jackett.has_password && (
              <Button stretched mode="bezeled" style={{ color: DEL_COLOR }} onClick={jackettRemovePass}>{t("settings.removePass")}</Button>
            )}
          </div>
        </Collapse>

        {/* Jellyfin */}
        {st.jellyfin.has_key && (
          <Collapse title={t("settings.jellyfin")}>
            <div style={{ padding: "8px 16px" }}>
              <Button stretched mode="bezeled" before={<Users size={18} />} onClick={openUsers}>
                {t("settings.manageUsers")}
              </Button>
            </div>
          </Collapse>
        )}

        {/* Web UIs */}
        {cfg.quick_links && (
          <Collapse title={t("settings.webUIs")}>
            <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>qBittorrent</Button>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>Jellyfin</Button>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.jackett)}>Jackett</Button>
            </div>
          </Collapse>
        )}

        <Section footer={t("settings.version", { version: cfg.version })} />
      </List>

      {/* New category modal */}
      <Modal
        open={dialog === "newCat"}
        onOpenChange={(o) => !o && setDialog(null)}
        header={<Modal.Header>{t("settings.newCategory")}</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <Input
            header={t("settings.nameLabel")}
            autoFocus
            value={newCatName}
            onChange={(e) => setNewCatName(e.target.value)}
            placeholder="Anime"
          />
          <Caption style={{ color: "var(--tgui--hint_color)" }}>{t("settings.libraryType")}</Caption>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {JF_TYPES.map(({ key, label, Icon }) => (
              <Button key={key} mode="bezeled" before={<Icon size={16} />} disabled={!newCatName.trim()} onClick={() => createCat(key)}>
                {label}
              </Button>
            ))}
          </div>
        </div>
      </Modal>

      {/* Jellyfin users modal */}
      <Modal
        open={dialog === "users"}
        onOpenChange={(o) => !o && setDialog(null)}
        header={<Modal.Header>{t("settings.jfUsers")}</Modal.Header>}
      >
        <List>
          <Section>
            {users?.map((u) => (
              <Cell
                key={u.id}
                after={
                  <Button mode="plain" size="s" style={{ color: DEL_COLOR }} onClick={() => delUser(u)}>
                    <Trash2 size={18} />
                  </Button>
                }
              >
                {u.name}
              </Cell>
            ))}
            {users?.length === 0 && <Cell>{t("settings.noUsers")}</Cell>}
          </Section>
        </List>
        <div style={{ padding: "8px 16px 16px" }}>
          <Button stretched mode="bezeled" before={<UserPlus size={18} />} onClick={() => setDialog("newUserName")}>
            {t("settings.addUser")}
          </Button>
        </div>
      </Modal>

      {/* Prompt sheets */}
      <PromptSheet
        title={t("settings.renameCategory")}
        label={t("settings.newName")}
        open={dialog === "renameCat" && !!renameCat}
        onSubmit={doRenameCat}
        onClose={() => { setRenameCat(null); setDialog(null); }}
      />
      <PromptSheet
        title={t("settings.qbPassTitle")}
        label={t("settings.newPass")}
        password
        open={dialog === "qbPass"}
        onSubmit={qbPass}
        onClose={() => setDialog(null)}
      />
      <PromptSheet
        title={t("settings.jackettPassTitle")}
        label={t("settings.newPassEmpty")}
        password
        submitText={t("common.save")}
        open={dialog === "jackettPass"}
        onSubmit={jackettPass}
        onClose={() => setDialog(null)}
      />
      <PromptSheet
        title={t("settings.newUser")}
        label={t("settings.username")}
        submitText={t("settings.next")}
        open={dialog === "newUserName"}
        onSubmit={(n) => { setNewUserName(n); setDialog("newUserPass"); }}
        onClose={() => setDialog("users")}
      />
      <PromptSheet
        title={t("settings.passwordFor", { name: newUserName })}
        label={t("settings.password")}
        password
        open={dialog === "newUserPass"}
        onSubmit={addUser}
        onClose={() => setDialog("users")}
      />
    </div>
  );
}
