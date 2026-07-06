import { useEffect, useState } from "react";
import { api } from "../api";
import { openExternal } from "../telegram";
import { useToast } from "../components/Toast";
import { Sheet } from "../components/Sheet";
import { PromptSheet } from "../components/PromptSheet";
import type { AppConfig, Category, JellyfinUser, Settings as SettingsData } from "../types";
import s from "./Settings.module.scss";

const JF_TYPES = [
  { key: "movies", label: "🎬 Movies" },
  { key: "tvshows", label: "📺 TV Shows" },
  { key: "music", label: "🎵 Music" },
  { key: "mixed", label: "📦 Other" },
];

export function Settings() {
  const toast = useToast();
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [st, setSt] = useState<SettingsData | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [users, setUsers] = useState<JellyfinUser[] | null>(null);

  // dialog state
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

  if (!cfg || !st) return <div className={s.spinner} />;

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
      <div className={s.screenTitle}>Settings</div>

      {/* Auto-structure */}
      <div className={`${s.card} ${s.tappable}`} onClick={toggleRename}>
        <div className={`${s.row} ${s.spread}`}>
          <div>
            <div className={s.titleText}>Auto-structure</div>
            <div className={s.subtitle}>{st.rename_mode === "pretty" ? "Smart (parse filenames)" : "Original structure"}</div>
          </div>
          <span className={`${s.chip} ${s.active}`}>{st.rename_mode === "pretty" ? "Smart" : "Original"}</span>
        </div>
      </div>

      {/* Language */}
      <div className={s.card}>
        <div className={`${s.row} ${s.spread}`}>
          <div className={s.titleText}>Language</div>
          <div className={s.chips}>
            <span className={`${s.chip}${st.lang === "ru" ? ` ${s.active}` : ""}`} onClick={() => setLang("ru")}>🇷🇺 RU</span>
            <span className={`${s.chip}${st.lang === "en" ? ` ${s.active}` : ""}`} onClick={() => setLang("en")}>🇬🇧 EN</span>
          </div>
        </div>
      </div>

      {/* Categories */}
      <div className={s.sectionLabel}>Categories</div>
      {cats.map((c) => (
        <div key={c.id} className={s.card}>
          <div className={`${s.row} ${s.spread}`}>
            <div className={s.grow} onClick={() => { setRenameCat(c); setDialog("renameCat"); }}>
              <div className={s.titleText}>{c.name}</div>
              <div className={`${s.subtitle} ${s.mono}`}>{c.path.replace("/media/", "")}</div>
            </div>
            <button className="destructive" onClick={() => delCat(c)}>🗑</button>
          </div>
        </div>
      ))}
      <button className="secondary full" onClick={() => setDialog("newCat")}>➕ Add category</button>

      {/* qBittorrent */}
      <div className={s.sectionLabel}>qBittorrent</div>
      <div className={s.card}>
        <div className={`${s.row} ${s.spread}`}>
          <span className={s.hint}>User: {st.qbittorrent.user}</span>
          <span className={s.hint}>{st.qbittorrent.is_perm ? "🔒 permanent" : "temporary"}</span>
        </div>
        <div className={s.btnRow} style={{ marginTop: 10 }}>
          <button className="secondary" onClick={() => setDialog("qbPass")}>Change pass</button>
          {!st.qbittorrent.is_perm && <button className="secondary" onClick={qbTemp}>Get temp</button>}
          <button className="secondary" onClick={qbRestart}>Restart</button>
        </div>
      </div>

      {/* Jackett */}
      <div className={s.sectionLabel}>Jackett</div>
      <div className={s.card}>
        <div className={`${s.row} ${s.spread}`}>
          <span className={s.hint}>API key: {st.jackett.has_key ? "✅" : "❌"}</span>
          <span className={s.hint}>Password: {st.jackett.has_password ? "🔒 set" : "🔓 public"}</span>
        </div>
        <div className={s.btnRow} style={{ marginTop: 10 }}>
          <button className="secondary" onClick={() => setDialog("jackettPass")}>Change pass</button>
          {st.jackett.has_password && <button className="destructive" onClick={jackettRemovePass}>Remove pass</button>}
        </div>
      </div>

      {/* Jellyfin */}
      {st.jellyfin.has_key && (
        <>
          <div className={s.sectionLabel}>Jellyfin</div>
          <button className="secondary full" onClick={openUsers}>👤 Manage users</button>
        </>
      )}

      {/* Quick links */}
      {cfg.quick_links && (
        <>
          <div className={s.sectionLabel}>Web UIs</div>
          <div className={s.btnRow}>
            <button className="secondary" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>qBittorrent</button>
            <button className="secondary" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>Jellyfin</button>
            <button className="secondary" onClick={() => openExternal(cfg.quick_links!.jackett)}>Jackett</button>
          </div>
        </>
      )}

      <div className={s.centerMsg} style={{ paddingTop: 24 }}>version {cfg.version}</div>

      {/* ---- dialogs ---- */}
      {dialog === "newCat" && (
        <Sheet title="New category" onClose={() => setDialog(null)}>
          <label>Name</label>
          <input autoFocus value={newCatName} onChange={(e) => setNewCatName(e.target.value)} placeholder="Anime" />
          <label>Library type</label>
          <div className={s.chips}>
            {JF_TYPES.map((t) => (
              <button key={t.key} className="secondary" disabled={!newCatName.trim()} onClick={() => createCat(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
        </Sheet>
      )}

      {dialog === "renameCat" && renameCat && (
        <PromptSheet
          title="Rename category"
          label="New name"
          onSubmit={doRenameCat}
          onClose={() => { setRenameCat(null); setDialog(null); }}
        />
      )}

      {dialog === "qbPass" && (
        <PromptSheet title="qBittorrent password" label="New password" password
          onSubmit={qbPass} onClose={() => setDialog(null)} />
      )}

      {dialog === "jackettPass" && (
        <PromptSheet title="Jackett admin password" label="New password (empty to remove)" password
          submitText="Save" onSubmit={jackettPass} onClose={() => setDialog(null)} />
      )}

      {dialog === "users" && users && (
        <Sheet title="Jellyfin users" onClose={() => setDialog(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {users.map((u) => (
              <div key={u.id} className={`${s.row} ${s.spread}`}>
                <span>{u.name}</span>
                <button className="destructive" onClick={() => delUser(u)}>🗑</button>
              </div>
            ))}
            {users.length === 0 && <div className={s.hint}>No users</div>}
            <button className="secondary full" onClick={() => setDialog("newUserName")}>➕ Add user</button>
          </div>
        </Sheet>
      )}

      {dialog === "newUserName" && (
        <PromptSheet title="New user" label="Username" submitText="Next"
          onSubmit={(n) => { setNewUserName(n); setDialog("newUserPass"); }}
          onClose={() => setDialog("users")} />
      )}

      {dialog === "newUserPass" && (
        <PromptSheet title={`Password for ${newUserName}`} label="Password" password
          onSubmit={addUser} onClose={() => setDialog("users")} />
      )}
    </div>
  );
}
