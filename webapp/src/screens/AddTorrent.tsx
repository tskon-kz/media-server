import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import type { Category } from "../types";
import s from "./AddTorrent.module.scss";

export function AddTorrent({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const [magnet, setMagnet] = useState("");
  const [cats, setCats] = useState<Category[]>([]);
  const [busy, setBusy] = useState(false);
  const [pick, setPick] = useState<null | { magnet?: string; file?: File }>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}); }, []);

  const submitMagnet = () => {
    const m = magnet.trim();
    if (!m.startsWith("magnet:")) { toast("Enter a valid magnet link", "err"); return; }
    if (cats.length === 0) addNow({ magnet: m });
    else setPick({ magnet: m });
  };

  const onFile = (f: File | undefined) => {
    if (!f) return;
    if (cats.length === 0) addNow({ file: f });
    else setPick({ file: f });
  };

  const addNow = async (what: { magnet?: string; file?: File }, cat?: Category) => {
    setPick(null);
    setBusy(true);
    try {
      if (what.magnet) await api.addMagnet(what.magnet, cat?.id);
      else if (what.file) await api.addTorrentFile(what.file, cat?.id);
      toast("✅ Added");
      setMagnet("");
      if (fileRef.current) fileRef.current.value = "";
      onAdded();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className={s.screenTitle}>Add torrent</div>

      <div className={s.card}>
        <label>Magnet link</label>
        <textarea
          placeholder="magnet:?xt=urn:btih:…"
          value={magnet}
          onChange={(e) => setMagnet(e.target.value)}
        />
        <button className="full" disabled={busy || !magnet.trim()} onClick={submitMagnet}>
          Add magnet
        </button>
      </div>

      <div className={s.card}>
        <label>Or upload a .torrent file</label>
        <input
          ref={fileRef}
          type="file"
          accept=".torrent"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
      </div>

      {pick && (
        <CategoryPicker
          categories={cats}
          title="Choose category"
          onPick={(c) => addNow(pick, c)}
          onClose={() => setPick(null)}
        />
      )}
    </div>
  );
}
