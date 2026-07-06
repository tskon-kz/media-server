import { useRef, useEffect, useState } from "react";
import {
  Box, Button, Drawer, FileInput, Loader, Stack, Text, Textarea, TextInput,
} from "@mantine/core";
import { Clapperboard, Film, Music, Package, Plus, Search as SearchIcon, Trash2, Tv } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { bytes } from "../format";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import { Collapse } from "../components/Collapse";
import { PromptSheet } from "../components/PromptSheet";
import { ListItem, ListPlaceholder, ListSection } from "../components/ui";
import PageHeader from "../components/PageHeader";
import type { Category, SearchResult } from "../types";

const DEL_COLOR = "var(--tg-theme-destructive-text-color)";

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

  // categories
  const [catDialog, setCatDialog] = useState<string | null>(null);
  const [newCatName, setNewCatName] = useState("");
  const [renameCat, setRenameCat] = useState<Category | null>(null);

  const JF_TYPES: { key: string; label: string; Icon: typeof Clapperboard }[] = [
    { key: "movies",  label: t("settings.movies"),  Icon: Film },
    { key: "tvshows", label: t("settings.tvShows"), Icon: Tv },
    { key: "music",   label: t("settings.music"),   Icon: Music },
    { key: "mixed",   label: t("settings.other"),   Icon: Package },
  ];

  const loadCats = () => api.categories().then((c) => setCats(c.categories)).catch(() => {});
  useEffect(() => { loadCats(); }, []); // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try { await fn(); } catch (e) { toast((e as Error).message, "err"); }
  };

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

  // ── categories ─────────────────────────────────────────────────────────────

  const createCat = (type: string) => guard(async () => {
    await api.createCategory(newCatName, type);
    setCatDialog(null); setNewCatName("");
    toast(t("settings.catAdded"));
    loadCats();
  });

  const doRenameCat = (name: string) => guard(async () => {
    if (renameCat) await api.renameCategory(renameCat.id, name);
    setRenameCat(null); setCatDialog(null);
    loadCats();
  });

  const delCat = (c: Category) => guard(async () => {
    await api.deleteCategory(c.id);
    toast(t("settings.catDeleted"));
    loadCats();
  });

  return (
    <div className="mb-16">
      <PageHeader title={t("add.title")} />

      <div className="mb-16">
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
        <Collapse title={t("add.manual")} className="mb-8">
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

        <Collapse title={t("settings.categories")}>
          <Stack gap={8} pt={4}>
            <ListSection>
              {cats.map((c) => (
                <ListItem
                  key={c.id}
                  subtitle={c.path.replace("/media/", "")}
                  after={
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      px={4}
                      style={{ color: DEL_COLOR }}
                      onClick={(e) => { e.stopPropagation(); delCat(c); }}
                    >
                      <Trash2 size={18} />
                    </Button>
                  }
                  onClick={() => { setRenameCat(c); setCatDialog("rename"); }}
                  multiline
                >
                  {c.name}
                </ListItem>
              ))}
            </ListSection>
            <Button
              fullWidth
              variant="light"
              leftSection={<Plus size={18} />}
              onClick={() => setCatDialog("new")}
            >
              {t("settings.addCategory")}
            </Button>
          </Stack>
        </Collapse>


        <Drawer
          opened={catDialog === "new"}
          onClose={() => setCatDialog(null)}
          title={t("settings.newCategory")}
          position="bottom"
          radius="lg"
          overlayProps={{ blur: 2 }}
        >
          <Stack gap={8} pb={16} px={4}>
            <TextInput
              autoFocus
              value={newCatName}
              onChange={(e) => setNewCatName(e.target.value)}
              placeholder="Anime"
            />
            <Text size="sm" c="dimmed">{t("settings.libraryType")}</Text>
            <Box style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {JF_TYPES.map(({ key, label, Icon }) => (
                <Button
                  key={key}
                  variant="light"
                  leftSection={<Icon size={16} />}
                  disabled={!newCatName.trim()}
                  onClick={() => createCat(key)}
                >
                  {label}
                </Button>
              ))}
            </Box>
          </Stack>
        </Drawer>

        <PromptSheet
          title={t("settings.renameCategory")}
          label={t("settings.newName")}
          open={catDialog === "rename" && !!renameCat}
          onSubmit={doRenameCat}
          onClose={() => { setRenameCat(null); setCatDialog(null); }}
        />

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
      </div>
    </div>
  );
}
