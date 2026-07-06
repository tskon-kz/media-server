import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Cell, List, Modal, Placeholder, Progress, Section, Spinner, Title } from "@telegram-apps/telegram-ui";
import { Clapperboard, Folder, FolderInput, Layers, RefreshCw, Trash2 } from "lucide-react";
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

  const doDelete = async (t: Torrent) => {
    setConfirmDel(null);
    setSelected(null);
    try { await api.deleteTorrent(t.hash); toast("Deleted"); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  const doMove = async (t: Torrent, cat: Category) => {
    setMoving(null);
    setSelected(null);
    try { await api.moveTorrent(t.hash, cat.id); toast(`Moved to ${cat.name}`); load(); }
    catch (e) { toast((e as Error).message, "err"); }
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

  if (torrents === null) {
    return <Spinner size="m" style={{ display: "block", margin: "40px auto" }} />;
  }

  return (
    <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 16px 4px" }}>
        <Title>Torrents</Title>
        <Button mode="plain" onClick={load}><RefreshCw size={20} /></Button>
      </div>

      {pull > 0 && (
        <div style={{ textAlign: "center", height: pull, color: "var(--tgui--hint_color)", fontSize: 14 }}>
          ↓ pull to refresh
        </div>
      )}

      {torrents.length === 0 ? (
        <Placeholder header="No torrents" description="Add a magnet link or .torrent file" />
      ) : (
        <List>
          <Section>
            {torrents.map((t) => (
              <Cell
                key={t.hash}
                before={<TorrentIcon state={t.state} />}
                subtitle={`${t.progress < 1 ? pct(t.progress) + " · " : ""}${bytes(t.size)}${t.dlspeed > 0 ? " · ↓ " + speed(t.dlspeed) : ""}`}
                description={t.progress < 1 ? <Progress value={t.progress * 100} style={{ marginTop: 6 }} /> : undefined}
                onClick={() => setSelected(t)}
                multiline
              >
                {t.name}
              </Cell>
            ))}
          </Section>
        </List>
      )}

      {/* Torrent actions */}
      <Modal
        open={!!selected}
        onOpenChange={(o) => !o && setSelected(null)}
        header={<Modal.Header>{selected?.name}</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          {cats.length > 0 && (
            <Button stretched mode="bezeled" before={<FolderInput size={18} />} onClick={() => { setMoving(selected); setSelected(null); }}>
              Move to category
            </Button>
          )}
          {selected?.renameable && (
            <Button stretched mode="bezeled" before={<Layers size={18} />} onClick={() => { setStructFor(selected); setSelected(null); }}>
              Structure
            </Button>
          )}
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => { setConfirmDel(selected); setSelected(null); }}>
            Delete
          </Button>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <Modal
        open={!!confirmDel}
        onOpenChange={(o) => !o && setConfirmDel(null)}
        header={<Modal.Header>Delete torrent?</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ color: "var(--tgui--hint_color)", fontSize: 14, marginBottom: 4 }}>
            "{confirmDel?.name}" and all its files will be removed.
          </div>
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => confirmDel && doDelete(confirmDel)}>
            Delete
          </Button>
          <Button stretched mode="bezeled" onClick={() => setConfirmDel(null)}>
            Cancel
          </Button>
        </div>
      </Modal>

      {/* Move to category */}
      <CategoryPicker
        categories={cats}
        open={!!moving}
        title="Move to category"
        onPick={(c) => moving && doMove(moving, c)}
        onClose={() => setMoving(null)}
      />

      {/* Structure picker */}
      <Modal
        open={!!structFor}
        onOpenChange={(o) => !o && setStructFor(null)}
        header={<Modal.Header>Structure</Modal.Header>}
      >
        <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <Button stretched mode="bezeled" before={<Clapperboard size={18} />} onClick={() => structFor && doStructure(structFor, "pretty")}>Pretty names</Button>
          <Button stretched mode="bezeled" before={<Folder size={18} />} onClick={() => structFor && doStructure(structFor, "flat")}>Original structure</Button>
          <Button stretched mode="bezeled" before={<Trash2 size={18} />} style={{ color: DEL_COLOR }} onClick={() => structFor && doStructure(structFor, "delete")}>Delete hardlinks</Button>
        </div>
      </Modal>
    </div>
  );
}
