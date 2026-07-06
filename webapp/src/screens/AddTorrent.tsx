import { useRef, useEffect, useState } from "react";
import { Box, Button, FileInput, Stack, Textarea, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import { ListSection } from "../components/ui";
import type { Category } from "../types";

export function AddTorrent({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const { t } = useTranslation();
  const [magnet, setMagnet] = useState("");
  const [cats, setCats] = useState<Category[]>([]);
  const [busy, setBusy] = useState(false);
  const [pick, setPick] = useState<null | { magnet?: string; file?: File }>(null);
  const [fileKey, setFileKey] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}); }, []);

  const submitMagnet = () => {
    const m = magnet.trim();
    if (!m.startsWith("magnet:")) { toast(t("add.invalidMagnet"), "err"); return; }
    if (cats.length === 0) addNow({ magnet: m });
    else setPick({ magnet: m });
  };

  const onFile = (f: File | null) => {
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
      toast(t("common.added"));
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
    <Box>
      <Box style={{ padding: "16px 16px 4px" }}>
        <Title order={3} style={{ color: "var(--tg-theme-text-color)" }}>
          {t("add.title")}
        </Title>
      </Box>

      <Box p={16}>
        <Stack gap={8}>
          <ListSection header={t("add.magnetSection")}>
            <Box p={12}>
              <Textarea
                ref={textareaRef}
                placeholder="magnet:?xt=urn:btih:…"
                value={magnet}
                onChange={(e) => setMagnet(e.target.value)}
                autosize
                minRows={2}
              />
            </Box>
          </ListSection>
          <Button
            fullWidth
            disabled={busy || !magnet.trim()}
            onClick={submitMagnet}
          >
            {t("add.addMagnet")}
          </Button>

          <ListSection header={t("add.fileSection")}>
            <Box p={12}>
              <FileInput
                key={fileKey}
                label={t("add.uploadLabel")}
                accept=".torrent"
                onChange={onFile}
                clearable
              />
            </Box>
          </ListSection>
        </Stack>
      </Box>

      <CategoryPicker
        categories={cats}
        open={!!pick}
        title={t("common.chooseCategory")}
        onPick={(c) => pick && addNow(pick, c)}
        onClose={() => setPick(null)}
      />
    </Box>
  );
}
