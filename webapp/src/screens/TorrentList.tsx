import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { bytes, pct, speed } from "../format";
import { haptic } from "../telegram";
import { useToast } from "../components/Toast";
import { Sheet } from "../components/Sheet";
import { CategoryPicker } from "../components/CategoryPicker";
import type { Category, Torrent } from "../types";
import s from "./TorrentList.module.scss";

export function TorrentList() {
  const toast = useToast();
  const [torrents, setTorrents] = useState<Torrent[] | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<Torrent | null>(null);
  const [moving, setMoving] = useState<Torrent | null>(null);
  const [structFor, setStructFor] = useState<Torrent | null>(null);
  const [confirmDel, setConfirmDel] = useState<Torrent | null>(null);
  const [pull, setPull] = useState(0);

  const load = useCallback(async () => {
    try {
      const [tr, c] = await Promise.all([api.torrents(), api.categories()]);
      setTorrents(tr.torrents);
      setCats(c.categories);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
      setTorrents([]);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [load]);

  // Lightweight pull-to-refresh.
  const startY = useRef<number | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    if (window.scrollY <= 0) startY.current = e.touches[0].clientY;
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (startY.current === null) return;
    const d = e.touches[0].clientY - startY.current;
    if (d > 0) setPull(Math.min(d, 80));
  };
  const onTouchEnd = () => {
    if (pull > 55) { haptic("light"); load(); }
    setPull(0);
    startY.current = null;
  };

  const doDelete = async (t: Torrent) => {
    setConfirmDel(null);
    setSelected(null);
    try {
      await api.deleteTorrent(t.hash);
      toast("Deleted");
      load();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  const doMove = async (t: Torrent, cat: Category) => {
    setMoving(null);
    setSelected(null);
    try {
      await api.moveTorrent(t.hash, cat.id);
      toast(`Moved to ${cat.name}`);
      load();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  const doStructure = async (t: Torrent, mode: "pretty" | "flat" | "delete") => {
    setStructFor(null);
    setSelected(null);
    try {
      const r = await api.structure(t.hash, mode);
      if (r.xdev) toast("Hardlink error: different partitions", "err");
      else if (mode === "pretty") toast(`Linked ${r.linked}, ${r.pending} need input`);
      else toast("Done");
      load();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  if (torrents === null) return <div className={s.spinner} />;

  return (
    <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <div className={`${s.row} ${s.spread}`}>
        <div className={s.screenTitle}>Torrents</div>
        <button className="ghost" onClick={() => load()}>↻</button>
      </div>
      {pull > 0 && <div className={s.hint} style={{ textAlign: "center", height: pull }}>↓ pull to refresh</div>}
      {err && <div className={`${s.card} ${s.errorText}`}>{err}</div>}
      {!err && torrents.length === 0 && <div className={s.centerMsg}>📭 List is empty</div>}

      {torrents.map((t) => (
        <div key={t.hash} className={`${s.card} ${s.tappable}`} onClick={() => setSelected(t)}>
          <div className={s.row}>
            <span className={s.iconLg}>{t.icon}</span>
            <div className={s.grow}>
              <div className={s.titleText}>{t.name}</div>
              <div className={s.subtitle}>
                {t.progress < 1 ? `${pct(t.progress)} · ` : ""}{bytes(t.size)}
                {t.dlspeed > 0 ? ` · ↓ ${speed(t.dlspeed)}` : ""}
              </div>
            </div>
          </div>
          {t.progress < 1 && (
            <div className={s.progress}><span style={{ width: `${t.progress * 100}%` }} /></div>
          )}
        </div>
      ))}

      {selected && (
        <Sheet title={selected.name} onClose={() => setSelected(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {cats.length > 0 && (
              <button className="secondary full" onClick={() => setMoving(selected)}>📁 Move to category</button>
            )}
            {selected.renameable && (
              <button className="secondary full" onClick={() => setStructFor(selected)}>🗂 Structure</button>
            )}
            <button className="destructive full" onClick={() => setConfirmDel(selected)}>🗑 Delete</button>
          </div>
        </Sheet>
      )}

      {confirmDel && (
        <Sheet title="Delete torrent?" onClose={() => setConfirmDel(null)}>
          <div className={s.hint} style={{ marginBottom: 12 }}>
            "{confirmDel.name}" and all its files will be removed. This cannot be undone.
          </div>
          <div className={s.btnRow}>
            <button className="secondary" onClick={() => setConfirmDel(null)}>Cancel</button>
            <button className="destructive" onClick={() => doDelete(confirmDel)}>Delete</button>
          </div>
        </Sheet>
      )}

      {moving && (
        <CategoryPicker
          categories={cats}
          title="Move to category"
          onPick={(c) => doMove(moving, c)}
          onClose={() => setMoving(null)}
        />
      )}

      {structFor && (
        <Sheet title="Structure" onClose={() => setStructFor(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button className="secondary full" onClick={() => doStructure(structFor, "pretty")}>🎬 Pretty names</button>
            <button className="secondary full" onClick={() => doStructure(structFor, "flat")}>📁 Original structure</button>
            <button className="destructive full" onClick={() => doStructure(structFor, "delete")}>🗑 Delete hardlinks</button>
          </div>
        </Sheet>
      )}
    </div>
  );
}
