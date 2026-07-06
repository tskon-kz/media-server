import { useRef, useEffect, useState } from "react";
import { Button, FileInput, List, Section, Textarea, Title } from "@telegram-apps/telegram-ui";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import type { Category } from "../types";

export function AddTorrent({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const [magnet, setMagnet] = useState("");
  const [cats, setCats] = useState<Category[]>([]);
  const [busy, setBusy] = useState(false);
  const [pick, setPick] = useState<null | { magnet?: string; file?: File }>(null);
  const [fileKey, setFileKey] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
      toast("Added");
      setMagnet("");
      setFileKey((k) => k + 1);
      onAdded();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ padding: "16px 16px 4px" }}>
        <Title>Add torrent</Title>
      </div>
      <List>
        <Section header="Magnet link">
          <Textarea
            ref={textareaRef}
            placeholder="magnet:?xt=urn:btih:…"
            value={magnet}
            onChange={(e) => setMagnet(e.target.value)}
          />
          <div style={{ padding: "0 16px 12px" }}>
            <Button stretched disabled={busy || !magnet.trim()} onClick={submitMagnet}>
              Add magnet
            </Button>
          </div>
        </Section>

        <Section header=".torrent file">
          <FileInput
            key={fileKey}
            label="Upload .torrent file"
            accept=".torrent"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </Section>
      </List>

      <CategoryPicker
        categories={cats}
        open={!!pick}
        title="Choose category"
        onPick={(c) => pick && addNow(pick, c)}
        onClose={() => setPick(null)}
      />
    </div>
  );
}
