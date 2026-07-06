import { useEffect, useState } from "react";
import {
  Button, Caption, Cell, Input, List, Modal, Section,
  SegmentedControl, Spinner, Switch, Title,
} from "@telegram-apps/telegram-ui";
import {
  Clapperboard, Film, Lock, Music, Package, Plus,
  Trash2, Tv, Unlock, UserPlus, Users,
} from "lucide-react";
import { api } from "../api";
import { openExternal } from "../telegram";
import { useToast } from "../components/Toast";
import { PromptSheet } from "../components/PromptSheet";
import type { AppConfig, Category, JellyfinUser, Settings as SettingsData } from "../types";

const JF_TYPES: { key: string; label: string; Icon: typeof Clapperboard }[] = [
  { key: "movies",  label: "Movies",   Icon: Film },
  { key: "tvshows", label: "TV Shows", Icon: Tv },
  { key: "music",   label: "Music",    Icon: Music },
  { key: "mixed",   label: "Other",    Icon: Package },
];

const DEL_COLOR = "var(--tgui--destructive_text_color)";

export function Settings() {
  const toast = useToast();
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
  };

  useEffect(() => { reload().catch((e) => toast((e as Error).message, "err")); }, []); // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try { await fn(); } catch (e) { toast((e as Error).message, "err"); }
  };

  if (!cfg || !st) return <Spinner size="m" style={{ display: "block", margin: "40px auto" }} />;

  const toggleRename = () => guard(async () => {
    const mode = st.rename_mode === "flat" ? "pretty" : "flat";
    await api.setRenameMode(mode);
    toast(mode === "pretty" ? "Smart structure on" : "Original structure");
    reload();
  });

  const setLang = (lang: string) => guard(async () => {
    await api.setLanguage(lang);
    toast(lang === "ru" ? "Русский" : "English");
    reload();
  });

  const createCat = (type: string) => guard(async () => {
    await api.createCategory(newCatName, type);
    setDialog(null); setNewCatName("");
    toast("Category added");
    reload();
  });

  const doRenameCat = (name: string) => guard(async () => {
    if (renameCat) await api.renameCategory(renameCat.id, name);
    setRenameCat(null); setDialog(null);
    reload();
  });

  const delCat = (c: Category) => guard(async () => {
    await api.deleteCategory(c.id);
    toast("Category deleted");
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
    toast("User created");
    const u = await api.jellyfinUsers();
    setUsers(u.users);
  });

  const delUser = (u: JellyfinUser) => guard(async () => {
    await api.deleteJellyfinUser(u.id);
    const list = await api.jellyfinUsers();
    setUsers(list.users);
  });

  const qbPass = (p: string) => guard(async () => {
    await api.setQbPassword(p); setDialog(null); toast("qB password changed"); reload();
  });
  const qbTemp = () => guard(async () => {
    const r = await api.fetchQbTemp();
    toast(r.found ? `Temp: ${r.password}` : "No temporary password", r.found ? "ok" : "err");
    reload();
  });
  const qbRestart = () => guard(async () => {
    const r = await api.restartQb(); toast(r.ok ? "qB restarting…" : "Restart failed", r.ok ? "ok" : "err");
  });
  const jackettPass = (p: string) => guard(async () => {
    await api.setJackettPassword(p); setDialog(null); toast("Jackett password updated"); reload();
  });
  const jackettRemovePass = () => guard(async () => {
    await api.setJackettPassword(""); toast("Jackett password removed"); reload();
  });

  return (
    <div>
      <div style={{ padding: "16px 16px 4px" }}>
        <Title>Settings</Title>
      </div>
      <List>
        {/* Auto-structure */}
        <Section>
          <Cell
            subtitle={st.rename_mode === "pretty" ? "Smart (parse filenames)" : "Original structure"}
            after={<Switch checked={st.rename_mode === "pretty"} onChange={toggleRename} />}
            multiline
          >
            Auto-structure
          </Cell>
        </Section>

        {/* Language */}
        <Section>
          <Cell
            after={
              <SegmentedControl>
                <SegmentedControl.Item selected={st.lang === "ru"} onClick={() => setLang("ru")}>RU</SegmentedControl.Item>
                <SegmentedControl.Item selected={st.lang === "en"} onClick={() => setLang("en")}>EN</SegmentedControl.Item>
              </SegmentedControl>
            }
          >
            Language
          </Cell>
        </Section>

        {/* Categories */}
        <Section header="Categories">
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
            Add category
          </Button>
        </div>

        {/* qBittorrent */}
        <Section header="qBittorrent">
          <Cell
            subtitle={`User: ${st.qbittorrent.user}`}
            after={st.qbittorrent.is_perm ? <Lock size={16} /> : undefined}
            multiline
          >
            Credentials
          </Cell>
        </Section>
        <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
          <Button stretched mode="bezeled" onClick={() => setDialog("qbPass")}>Change pass</Button>
          {!st.qbittorrent.is_perm && <Button stretched mode="bezeled" onClick={qbTemp}>Get temp</Button>}
          <Button stretched mode="bezeled" onClick={qbRestart}>Restart</Button>
        </div>

        {/* Jackett */}
        <Section header="Jackett">
          <Cell
            subtitle={`API key: ${st.jackett.has_key ? "available" : "missing"}`}
            after={st.jackett.has_password ? <Lock size={16} /> : <Unlock size={16} />}
            multiline
          >
            Jackett
          </Cell>
        </Section>
        <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
          <Button stretched mode="bezeled" onClick={() => setDialog("jackettPass")}>Change pass</Button>
          {st.jackett.has_password && (
            <Button stretched mode="bezeled" style={{ color: DEL_COLOR }} onClick={jackettRemovePass}>Remove pass</Button>
          )}
        </div>

        {/* Jellyfin */}
        {st.jellyfin.has_key && (
          <div style={{ padding: "8px 16px" }}>
            <Button stretched mode="bezeled" before={<Users size={18} />} onClick={openUsers}>
              Manage Jellyfin users
            </Button>
          </div>
        )}

        {/* Quick links */}
        {cfg.quick_links && (
          <>
            <Section header="Web UIs" />
            <div style={{ padding: "8px 16px", display: "flex", gap: 8 }}>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>qBittorrent</Button>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>Jellyfin</Button>
              <Button stretched mode="bezeled" onClick={() => openExternal(cfg.quick_links!.jackett)}>Jackett</Button>
            </div>
          </>
        )}

        <Section footer={`version ${cfg.version}`} />
      </List>

      {/* New category dialog */}
      <Modal
        open={dialog === "newCat"}
        onOpenChange={(o) => !o && setDialog(null)}
        header={<Modal.Header>New category</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <Input
            header="Name"
            autoFocus
            value={newCatName}
            onChange={(e) => setNewCatName(e.target.value)}
            placeholder="Anime"
          />
          <Caption style={{ color: "var(--tgui--hint_color)" }}>Library type</Caption>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {JF_TYPES.map(({ key, label, Icon }) => (
              <Button key={key} mode="bezeled" before={<Icon size={16} />} disabled={!newCatName.trim()} onClick={() => createCat(key)}>
                {label}
              </Button>
            ))}
          </div>
        </div>
      </Modal>

      {/* Jellyfin users dialog */}
      <Modal
        open={dialog === "users"}
        onOpenChange={(o) => !o && setDialog(null)}
        header={<Modal.Header>Jellyfin users</Modal.Header>}
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
            {users?.length === 0 && <Cell>No users yet</Cell>}
          </Section>
        </List>
        <div style={{ padding: "8px 16px 16px" }}>
          <Button stretched mode="bezeled" before={<UserPlus size={18} />} onClick={() => setDialog("newUserName")}>
            Add user
          </Button>
        </div>
      </Modal>

      {/* PromptSheets */}
      <PromptSheet
        title="Rename category"
        label="New name"
        open={dialog === "renameCat" && !!renameCat}
        onSubmit={doRenameCat}
        onClose={() => { setRenameCat(null); setDialog(null); }}
      />
      <PromptSheet
        title="qBittorrent password"
        label="New password"
        password
        open={dialog === "qbPass"}
        onSubmit={qbPass}
        onClose={() => setDialog(null)}
      />
      <PromptSheet
        title="Jackett admin password"
        label="New password (empty to remove)"
        password
        submitText="Save"
        open={dialog === "jackettPass"}
        onSubmit={jackettPass}
        onClose={() => setDialog(null)}
      />
      <PromptSheet
        title="New user"
        label="Username"
        submitText="Next"
        open={dialog === "newUserName"}
        onSubmit={(n) => { setNewUserName(n); setDialog("newUserPass"); }}
        onClose={() => setDialog("users")}
      />
      <PromptSheet
        title={`Password for ${newUserName}`}
        label="Password"
        password
        open={dialog === "newUserPass"}
        onSubmit={addUser}
        onClose={() => setDialog("users")}
      />
    </div>
  );
}
