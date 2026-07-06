import { useEffect, useState } from "react";
import {
  Box, Button, Drawer, Loader, SegmentedControl, Stack, Switch, Text, Title,
} from "@mantine/core";
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
import AppSection from "../components/AppSection.tsx";
import { ListItem, ListSection } from "../components/ui";
import type { AppConfig, Category, JellyfinUser, Settings as SettingsData } from "../types";

const DEL_COLOR = "var(--tg-theme-destructive-text-color)";

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

  if (!cfg || !st) {
    return (
      <Box style={{ textAlign: "center", paddingTop: 60 }}>
        <Loader size="md" />
      </Box>
    );
  }

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
    <Box>
      <Box style={{ padding: "16px 16px 4px" }}>
        <Title order={3} style={{ color: "var(--tg-theme-text-color)" }}>
          {t("settings.title")}
        </Title>
      </Box>

      <Box p={16}>
        <Stack gap={8}>
          {/* Auto-structure toggle */}
          <ListSection>
            <ListItem
              subtitle={st.rename_mode === "pretty" ? t("settings.smartSub") : t("settings.originalSub")}
              after={
                <Switch
                  checked={st.rename_mode === "pretty"}
                  onChange={toggleRename}
                  onClick={(e) => e.stopPropagation()}
                />
              }
              multiline
            >
              {t("settings.autoStructure")}
            </ListItem>
          </ListSection>

          {/* Language */}
          <AppSection title={t("settings.language")}>
            <Box px={12} pb={12}>
              <SegmentedControl
                fullWidth
                value={st.lang}
                onChange={setLang}
                data={[
                  { value: "ru", label: "RU" },
                  { value: "en", label: "EN" },
                ]}
              />
            </Box>
          </AppSection>

          {/* Appearance */}
          <AppSection title={t("settings.appearance")}>
            <Box px={12} pb={12}>
              <SegmentedControl
                fullWidth
                value={themeMode}
                onChange={(v) => setThemeMode(v as ThemeMode)}
                data={[
                  { value: "auto",  label: t("settings.auto") },
                  { value: "light", label: t("settings.light") },
                  { value: "dark",  label: t("settings.dark") },
                ]}
              />
            </Box>
          </AppSection>

          {/* Categories */}
          <Collapse title={t("settings.categories")}>
            <ListSection>
              {cats.map((c) => (
                <ListItem
                  key={c.id}
                  subtitle={c.path.replace("/media/", "")}
                  after={
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      px={4}
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
                </ListItem>
              ))}
            </ListSection>
            <Button
              fullWidth
              variant="light"
              leftSection={<Plus size={18} />}
              onClick={() => setDialog("newCat")}
            >
              {t("settings.addCategory")}
            </Button>
          </Collapse>

          {/* qBittorrent */}
          <Collapse title={t("settings.qb")}>
            <ListSection>
              <ListItem
                subtitle={t("settings.userSub", { user: st.qbittorrent.user })}
                after={st.qbittorrent.is_perm ? <Lock size={16} /> : undefined}
                multiline
              >
                {t("settings.credentials")}
              </ListItem>
            </ListSection>
            <Stack gap={8}>
              <Button fullWidth variant="light" onClick={() => setDialog("qbPass")}>{t("settings.changePass")}</Button>
              {!st.qbittorrent.is_perm && <Button fullWidth variant="light" onClick={qbTemp}>{t("settings.getTemp")}</Button>}
              <Button fullWidth variant="light" onClick={qbRestart}>{t("settings.restart")}</Button>
            </Stack>
          </Collapse>

          {/* Jackett */}
          <Collapse title={t("settings.jackett")}>
            <ListSection>
              <ListItem
                subtitle={t("settings.apiKey", { status: t(st.jackett.has_key ? "settings.keyAvailable" : "settings.keyMissing") })}
                after={st.jackett.has_password ? <Lock size={16} /> : <Unlock size={16} />}
                multiline
              >
                {t("settings.jackett")}
              </ListItem>
            </ListSection>
            <Stack gap={8}>
              <Button fullWidth variant="light" onClick={() => setDialog("jackettPass")}>{t("settings.changePass")}</Button>
              {st.jackett.has_password && (
                <Button fullWidth variant="light" style={{ color: DEL_COLOR }} onClick={jackettRemovePass}>
                  {t("settings.removePass")}
                </Button>
              )}
            </Stack>
          </Collapse>

          {/* Jellyfin */}
          {st.jellyfin.has_key && (
            <Collapse title={t("settings.jellyfin")}>
              <Button fullWidth variant="light" leftSection={<Users size={18} />} onClick={openUsers}>
                {t("settings.manageUsers")}
              </Button>
            </Collapse>
          )}

          {/* Web UIs */}
          {cfg.quick_links && (
            <Collapse title={t("settings.webUIs")}>
              <Stack gap={8}>
                <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>qBittorrent</Button>
                <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>Jellyfin</Button>
                <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jackett)}>Jackett</Button>
              </Stack>
            </Collapse>
          )}

          <Text size="xs" c="dimmed" ta="center">
            {t("settings.version", { version: cfg.version })}
          </Text>
        </Stack>
      </Box>

      {/* New category modal */}
      <Drawer
        opened={dialog === "newCat"}
        onClose={() => setDialog(null)}
        title={t("settings.newCategory")}
        position="bottom"
        radius="lg"
        overlayProps={{ blur: 2 }}
      >
        <Stack gap={8} pb={16} px={4}>
          <input
            autoFocus
            value={newCatName}
            onChange={(e) => setNewCatName(e.target.value)}
            placeholder="Anime"
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid rgba(128,128,128,0.3)",
              background: "var(--tg-theme-section-bg-color)",
              color: "var(--tg-theme-text-color)",
              fontSize: 16,
              width: "100%",
              boxSizing: "border-box",
            }}
          />
          <Text size="sm" c="dimmed">{t("settings.libraryType")}</Text>
          <Box style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {JF_TYPES.map(({ key, label, Icon }) => (
              <Button
                key={key}
                variant="light"
                leftSection={<Icon size={16} />}
                disabled={!newCatName.trim()}
                onClick={() => createCat(key)}
              >
                {label}
              </Button>
            ))}
          </Box>
        </Stack>
      </Drawer>

      {/* Jellyfin users modal */}
      <Drawer
        opened={dialog === "users"}
        onClose={() => setDialog(null)}
        title={t("settings.jfUsers")}
        position="bottom"
        radius="lg"
        overlayProps={{ blur: 2 }}
      >
        <Stack gap={8} pb={16} px={4}>
          <ListSection>
            {users?.map((u) => (
              <ListItem
                key={u.id}
                after={
                  <Button
                    variant="subtle"
                    size="compact-sm"
                    px={4}
                    style={{ color: DEL_COLOR }}
                    onClick={() => delUser(u)}
                  >
                    <Trash2 size={18} />
                  </Button>
                }
              >
                {u.name}
              </ListItem>
            ))}
            {users?.length === 0 && (
              <ListItem>{t("settings.noUsers")}</ListItem>
            )}
          </ListSection>
          <Button fullWidth variant="light" leftSection={<UserPlus size={18} />} onClick={() => setDialog("newUserName")}>
            {t("settings.addUser")}
          </Button>
        </Stack>
      </Drawer>

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
    </Box>
  );
}
