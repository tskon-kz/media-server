import { useEffect, useState } from "react";
import {
  Box, Button, Drawer, Loader, SegmentedControl, Stack, Text,
} from "@mantine/core";
import {
  Lock, Trash2, Unlock, UserPlus, Users,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { openExternal } from "../telegram";
import { useToast } from "../components/Toast";
import { useTheme, type ThemeMode } from "../theme";
import { setAppLanguage } from "../i18n";
import { Collapse } from "../components/Collapse";
import { PromptSheet } from "../components/PromptSheet";
import Section from "../components/Section.tsx";
import { ListItem, ListSection } from "../components/ui";
import type { AppConfig, JellyfinUser, Settings as SettingsData } from "../types";
import PageHeader from "../components/PageHeader.tsx";

const DEL_COLOR = "var(--tg-theme-destructive-text-color)";

export function Settings() {
  const toast = useToast();
  const { t } = useTranslation();
  const { mode: themeMode, setMode: setThemeMode } = useTheme();
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [settingsData, setSettingsData] = useState<SettingsData | null>(null);
  const [users, setUsers] = useState<JellyfinUser[] | null>(null);
  const [dialog, setDialog] = useState<string | null>(null);
  const [newUserName, setNewUserName] = useState("");

  const reload = async () => {
    const [c, s] = await Promise.all([api.config(), api.settings()]);
    setCfg(c); setSettingsData(s);
    setAppLanguage(s.lang);
  };

  useEffect(() => { reload().catch((e) => toast((e as Error).message, "err")); }, []); // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try { await fn(); } catch (e) { toast((e as Error).message, "err"); }
  };

  if (!cfg || !settingsData) {
    return (
      <Box style={{ textAlign: "center", paddingTop: 60 }}>
        <Loader size="md" />
      </Box>
    );
  }

  const setLang = (lang: string) => guard(async () => {
    await api.setLanguage(lang);
    setAppLanguage(lang);
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
      <PageHeader title={t("settings.title")} />

      <Box p={16}>
        <Stack gap={8}>
          <Section title={t("settings.autoStructure")} className="mb-16">
            <SegmentedControl
              fullWidth
              value={settingsData.rename_mode}
              onChange={(v) => guard(async () => {
                await api.setRenameMode(v as "flat" | "pretty");
                toast(v === "pretty" ? t("settings.smartOn") : t("settings.originalOn"));
                reload();
              })}
              data={[
                { value: "flat",   label: t("settings.originalSub") },
                { value: "pretty", label: t("settings.smartSub") },
              ]}
            />
          </Section>

          <Section className="mb-16" title={t("settings.language")}>
            <SegmentedControl
              fullWidth
              value={settingsData.lang}
              onChange={setLang}
              data={[
                { value: "ru", label: "RU" },
                { value: "en", label: "EN" },
              ]}
            />
          </Section>

          <Section className="mb-16" title={t("settings.appearance")}>
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
          </Section>

          <Collapse className="mb-12" title={t("settings.qb")}>
            <ListSection>
              <ListItem
                subtitle={t("settings.userSub", { user: settingsData.qbittorrent.user })}
                after={settingsData.qbittorrent.is_perm ? <Lock size={16} /> : undefined}
                multiline
              >
                {t("settings.credentials")}
              </ListItem>
            </ListSection>
            <Stack gap={8}>
              <Button fullWidth variant="light" onClick={() => setDialog("qbPass")}>{t("settings.changePass")}</Button>
              {!settingsData.qbittorrent.is_perm && <Button fullWidth variant="light" onClick={qbTemp}>{t("settings.getTemp")}</Button>}
              <Button fullWidth variant="light" onClick={qbRestart}>{t("settings.restart")}</Button>
              {cfg.quick_links && (
                <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>
                  {t("settings.openWebUI")}
                </Button>
              )}
            </Stack>
          </Collapse>

          <Collapse className="mb-12" title={t("settings.jackett")}>
            <ListSection>
              <ListItem
                subtitle={t("settings.apiKey", { status: t(settingsData.jackett.has_key ? "settings.keyAvailable" : "settings.keyMissing") })}
                after={settingsData.jackett.has_password ? <Lock size={16} /> : <Unlock size={16} />}
                multiline
              >
                {t("settings.jackett")}
              </ListItem>
            </ListSection>
            <Stack gap={8}>
              <Button fullWidth variant="light" onClick={() => setDialog("jackettPass")}>{t("settings.changePass")}</Button>
              {settingsData.jackett.has_password && (
                <Button fullWidth variant="light" style={{ color: DEL_COLOR }} onClick={jackettRemovePass}>
                  {t("settings.removePass")}
                </Button>
              )}
              {cfg.quick_links && (
                <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jackett)}>
                  {t("settings.openWebUI")}
                </Button>
              )}
            </Stack>
          </Collapse>

          {settingsData.jellyfin.has_key && (
            <Collapse className="mb-12" title={t("settings.jellyfin")}>
              <Stack gap={8}>
                <Button fullWidth variant="light" leftSection={<Users size={18} />} onClick={openUsers}>
                  {t("settings.manageUsers")}
                </Button>
                {cfg.quick_links && (
                  <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>
                    {t("settings.openWebUI")}
                  </Button>
                )}
              </Stack>
            </Collapse>
          )}

          <Text size="xs" c="dimmed" ta="center">
            {t("settings.version", { version: cfg.version })}
          </Text>
        </Stack>
      </Box>

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
