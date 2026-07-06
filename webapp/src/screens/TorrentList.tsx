import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Cell, List, Modal, Placeholder, Progress, Section, Spinner, Title } from "@telegram-apps/telegram-ui";
import { Clapperboard, Folder, FolderInput, Layers, RefreshCw, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { bytes, pct, speed } from "../format";
import { haptic } from "../telegram";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import { TorrentIcon } from "../icons";
import type { Category, Torrent } from "../types";

const DEL_COLOR = "var(--tgui--destructive_text_color)";

export function TorrentList() {
  const toast = useToast();
  const { t } = useTranslation();
  const [torrents, setTorrents] = useState<Torrent[] | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
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
    } catch (e) {
      toast((e as Error).message, "err");
      setTorrents([]);
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [load]);

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

  const doDelete = async (tor: Torrent) => {
    setConfirmDel(null);
    setSelected(null);
    try { await api.deleteTorrent(tor.hash); toast(t("torrents.deleted")); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  const doMove = async (tor: Torrent, cat: Category) => {
    setMoving(null);
    setSelected(null);
    try { await api.moveTorrent(tor.hash, cat.id); toast(t("torrents.moved", { name: cat.name })); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  const doStructure = async (tor: Torrent, mode: "pretty" | "flat" | "delete") => {
    setStructFor(null);
    setSelected(null);
    try {
      const r = await api.structure(tor.hash, mode);
      if (r.xdev) toast(t("torrents.xdev"), "err");
      else if (mode === "pretty") toast(t("torrents.linked", { n: r.linked, pending: r.pending }));
      else toast(t("common.done"));
      load();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  if (torrents === null) {
    return <Spinner size="m" style={{ display: "block", margin: "40px auto" }} />;
  }

  return (
    <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 16px 4px" }}>
        <Title>{t("torrents.title")}</Title>
        <Button mode="plain" onClick={load}><RefreshCw size={20} /></Button>
      </div>

      {pull > 0 && (
        <div style={{ textAlign: "center", height: pull, color: "var(--tgui--hint_color)", fontSize: 14 }}>
          {t("torrents.pull")}
        </div>
      )}

      {torrents.length === 0 ? (
        <Placeholder header={t("torrents.empty")} description={t("torrents.emptyHint")} />
      ) : (
        <List>
          <Section>
            {torrents.map((tor) => (
              <Cell
                key={tor.hash}
                before={<TorrentIcon state={tor.state} />}
                subtitle={`${tor.progress < 1 ? pct(tor.progress) + " · " : ""}${bytes(tor.size)}${tor.dlspeed > 0 ? " · ↓ " + speed(tor.dlspeed) : ""}`}
                description={tor.progress < 1 ? <Progress value={tor.progress * 100} style={{ marginTop: 6 }} /> : undefined}
                onClick={() => setSelected(tor)}
                multiline
              >
                {tor.name}
              </Cell>
            ))}
          </Section>
        </List>
      )}

      {/* Torrent action sheet */}
      <Modal
        open={!!selected}
        onOpenChange={(o) => !o && setSelected(null)}
        header={<Modal.Header>{selected?.name}</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          {cats.length > 0 && (
            <Button stretched mode="bezeled" before={<FolderInput size={18} />} onClick={() => { setMoving(selected); setSelected(null); }}>
              {t("torrents.move")}
            </Button>
          )}
          {selected?.renameable && (
            <Button stretched mode="bezeled" before={<Layers size={18} />} onClick={() => { setStructFor(selected); setSelected(null); }}>
              {t("torrents.structure")}
            </Button>
          )}
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => { setConfirmDel(selected); setSelected(null); }}>
            {t("common.delete")}
          </Button>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <Modal
        open={!!confirmDel}
        onOpenChange={(o) => !o && setConfirmDel(null)}
        header={<Modal.Header>{t("torrents.deleteTitle")}</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ color: "var(--tgui--hint_color)", fontSize: 14, marginBottom: 4 }}>
            {t("torrents.deleteBody", { name: confirmDel?.name })}
          </div>
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => confirmDel && doDelete(confirmDel)}>
            {t("common.delete")}
          </Button>
          <Button stretched mode="bezeled" onClick={() => setConfirmDel(null)}>
            {t("common.cancel")}
          </Button>
        </div>
      </Modal>

      {/* Move to category */}
      <CategoryPicker
        categories={cats}
        open={!!moving}
        title={t("torrents.move")}
        onPick={(c) => moving && doMove(moving, c)}
        onClose={() => setMoving(null)}
      />

      {/* Structure mode picker */}
      <Modal
        open={!!structFor}
        onOpenChange={(o) => !o && setStructFor(null)}
        header={<Modal.Header>{t("torrents.structure")}</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <Button stretched mode="bezeled" before={<Clapperboard size={18} />} onClick={() => structFor && doStructure(structFor, "pretty")}>{t("torrents.pretty")}</Button>
          <Button stretched mode="bezeled" before={<Folder size={18} />} onClick={() => structFor && doStructure(structFor, "flat")}>{t("torrents.original")}</Button>
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => structFor && doStructure(structFor, "delete")}>{t("torrents.delLinks")}</Button>
        </div>
      </Modal>
    </div>
  );
}
