import { useRef, useEffect, useState } from "react";
import { Box, Button, FileInput, Loader, Stack, Textarea, TextInput } from "@mantine/core";
import { Search as SearchIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { bytes } from "../format";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import { Collapse } from "../components/Collapse";
import { ListItem, ListPlaceholder, ListSection } from "../components/ui";
import PageHeader from "../components/PageHeader";
import type { Category, SearchResult } from "../types";

export function AddTorrent({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const { t } = useTranslation();
  const [cats, setCats] = useState<Category[]>([]);

  // magnet / file
  const [magnet, setMagnet] = useState("");
  const [busy, setBusy] = useState(false);
  const [fileKey, setFileKey] = useState(0);
  const [pick, setPick] = useState<null | { magnet?: string; file?: File }>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // search
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchPick, setSearchPick] = useState<SearchResult | null>(null);

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}); }, []);

  // ── magnet / file ──────────────────────────────────────────────────────────

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

  // ── search ─────────────────────────────────────────────────────────────────

  const runSearch = async () => {
    const query = q.trim();
    if (!query) return;
    setSearching(true);
    try {
      const r = await api.search(query);
      setResults(r.results);
    } catch (e) {
      toast((e as Error).message, "err");
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const choose = (r: SearchResult) => {
    if (cats.length === 0) searchAddNow(r);
    else setSearchPick(r);
  };

  const searchAddNow = async (r: SearchResult, cat?: Category) => {
    setSearchPick(null);
    try { await api.searchAdd(r, cat?.id); toast(t("common.added")); onAdded(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <Box>
      <PageHeader title={t("add.title")} />

      <div className="mb-32">
        <TextInput
          placeholder={t("search.placeholder")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
          rightSection={
            <Button
              variant="subtle"
              size="compact-sm"
              px={4}
              onClick={runSearch}
              disabled={searching || !q.trim()}
            >
              <SearchIcon size={18} />
            </Button>
          }
          rightSectionWidth={40}
        />

        {searching && (
          <Box style={{ textAlign: "center", padding: "24px 0" }}>
            <Loader size="md" />
          </Box>
        )}

        {results !== null && !searching && results.length === 0 && (
          <ListPlaceholder header={t("search.empty")} description={t("search.emptyHint")} />
        )}

        {results && results.length > 0 && (
            <ListSection>
              {results.map((r, i) => (
                <ListItem
                  key={i}
                  subtitle={`${t("search.seeders", { n: r.seeders })} · ${bytes(r.size)} · ${r.tracker}${r.date ? " · " + r.date.slice(0, 10) : ""}`}
                  onClick={() => choose(r)}
                  multiline
                >
                  {r.title}
                </ListItem>
              ))}
            </ListSection>
          )}
      </div>

      <div>
        <Collapse title={t("add.manual")}>
          <Stack gap={8} pt={4}>
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
            <Button fullWidth disabled={busy || !magnet.trim()} onClick={submitMagnet}>
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
        </Collapse>
      </div>

      <CategoryPicker
        categories={cats}
        open={!!pick}
        title={t("common.chooseCategory")}
        onPick={(c) => pick && addNow(pick, c)}
        onClose={() => setPick(null)}
      />
      <CategoryPicker
        categories={cats}
        open={!!searchPick}
        title={t("common.chooseCategory")}
        onPick={(c) => searchPick && searchAddNow(searchPick, c)}
        onClose={() => setSearchPick(null)}
      />
    </Box>
  );
}
