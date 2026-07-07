import {useEffect, useRef, useState} from "react"
import {Box, Button, Drawer, Loader, Pagination, Stack, Text, TextInput,} from "@mantine/core"
import {Clapperboard, Film, Music, Package, Plus, Search as SearchIcon, Trash2, Tv, X} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes} from "@/format"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {Collapse} from "@/components/Collapse"
import {PromptSheet} from "@/components/PromptSheet"
import {ListItem, ListPlaceholder, ListSection} from "@/components/ui"
import PageHeader from "@/components/PageHeader"
import type {Category, SearchResult} from "@/types"
import {useAppDispatch, useAppSelector} from "@/store"
import {setQuery, setLoading, setResults, clearSearch} from "@/store/slices/searchSlice"
import {ManualContent} from "./components/ManualContent"
import {CategoriesContent} from "./components/CategoriesContent"

export function AddTorrent({onAdded}: { onAdded: () => void }) {
  const {t} = useTranslation()
  const dispatch = useAppDispatch()
  const [cats, setCats] = useState<Category[]>([])

  // magnet / file
  const [magnet, setMagnet] = useState("")
  const [busy, setBusy] = useState(false)
  const [fileKey, setFileKey] = useState(0)
  const [pick, setPick] = useState<null | { magnet?: string; file?: File }>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // search state from Redux
  const query = useAppSelector((s) => s.search.query)
  const results = useAppSelector((s) => s.search.results)
  const searching = useAppSelector((s) => s.search.loading)
  const searchPage = useAppSelector((s) => s.search.page)
  const searchTotal = useAppSelector((s) => s.search.total)
  const PAGE_SIZE = 5

  const [searchPick, setSearchPick] = useState<SearchResult | null>(null)

  // categories
  const [catDialog, setCatDialog] = useState<string | null>(null)
  const [newCatName, setNewCatName] = useState("")
  const [renameCat, setRenameCat] = useState<Category | null>(null)
  const [confirmDelCat, setConfirmDelCat] = useState<Category | null>(null)

  const JF_TYPES: { key: string; label: string; Icon: typeof Clapperboard }[] = [
    {key: "movies", label: t("settings.movies"), Icon: Film},
    {key: "tvshows", label: t("settings.tvShows"), Icon: Tv},
    {key: "music", label: t("settings.music"), Icon: Music},
    {key: "mixed", label: t("settings.other"), Icon: Package},
  ]

  const loadCats = () => api.categories().then((c) => setCats(c.categories)).catch(() => {})
  useEffect(() => {
    loadCats()
  }, []) // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try {
      await fn()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  // ── magnet / file ──────────────────────────────────────────────────────────

  const submitMagnet = () => {
    const m = magnet.trim()
    if (!m.startsWith("magnet:")) {
      toast(t("add.invalidMagnet"), "err")
      return
    }
    if (cats.length === 0) addNow({magnet: m})
    else setPick({magnet: m})
  }

  const onFile = (f: File | null) => {
    if (!f) return
    if (cats.length === 0) addNow({file: f})
    else setPick({file: f})
  }

  const addNow = async (what: { magnet?: string; file?: File }, cat?: Category) => {
    setPick(null)
    setBusy(true)
    try {
      if (what.magnet) await api.addMagnet(what.magnet, cat?.id)
      else if (what.file) await api.addTorrentFile(what.file, cat?.id)
      toast(t("common.added"))
      setMagnet("")
      setFileKey((k) => k + 1)
      onAdded()
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setBusy(false)
    }
  }

  // ── search ─────────────────────────────────────────────────────────────────

  const runSearch = async (page = 1) => {
    const q = query.trim()
    if (!q) return
    dispatch(setLoading(true))
    try {
      const r = await api.search(q, page, PAGE_SIZE)
      dispatch(setResults({results: r.results, total: r.total, page}))
    } catch (e) {
      toast((e as Error).message, "err")
      dispatch(setResults({results: [], total: 0, page}))
    } finally {
      dispatch(setLoading(false))
    }
  }

  const choose = (r: SearchResult) => {
    if (cats.length === 0) searchAddNow(r)
    else setSearchPick(r)
  }

  const searchAddNow = async (r: SearchResult, cat?: Category) => {
    setSearchPick(null)
    try {
      await api.searchAdd(r, cat?.id)
      toast(t("common.added"))
      onAdded()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  // ── categories ─────────────────────────────────────────────────────────────

  const createCat = (type: string) => guard(async () => {
    await api.createCategory(newCatName, type)
    setCatDialog(null)
    setNewCatName("")
    toast(t("settings.catAdded"))
    loadCats()
  })

  const doRenameCat = (name: string) => guard(async () => {
    if (renameCat) await api.renameCategory(renameCat.id, name)
    setRenameCat(null)
    setCatDialog(null)
    loadCats()
  })

  const delCat = (c: Category) => guard(async () => {
    setConfirmDelCat(null)
    await api.deleteCategory(c.id)
    toast(t("settings.catDeleted"))
    loadCats()
  })

  return (
    <div className="mb-16">
      <PageHeader title={t("add.title")}/>

      <div className="mb-16">
        <TextInput
          size="lg"
          radius="lg"
          className="mb-8"
          placeholder={t("search.placeholder")}
          value={query}
          onChange={(e) => dispatch(setQuery(e.target.value))}
          onKeyDown={(e) => e.key === "Enter" && runSearch(1)}
          rightSection={
            results !== null ? (
              <Button variant="subtle" size="compact-sm" px={4} onClick={() => dispatch(clearSearch())}>
                <X size={18}/>
              </Button>
            ) : (
              <Button
                variant="subtle"
                size="compact-sm"
                px={4}
                onClick={() => runSearch(1)}
                disabled={searching || !query.trim()}
              >
                <SearchIcon size={18}/>
              </Button>
            )
          }
          rightSectionWidth={40}
        />

        {searching && (
          <Box style={{textAlign: "center", padding: "24px 0"}}>
            <Loader size="md"/>
          </Box>
        )}

        {results !== null && !searching && results.length === 0 && (
          <ListPlaceholder header={t("search.empty")} description={t("search.emptyHint")}/>
        )}

        {results && results.length > 0 && (
          <>
            <ListSection style={{borderRadius: 16, overflow: 'hidden'}}>
              {results.map((r, i) => (
                <ListItem
                  key={i}
                  subtitle={`${t("search.seeders", {n: r.seeders})} · ${bytes(r.size)} · ${r.tracker}${r.date ? " · " + r.date.slice(0, 10) : ""}`}
                  after={
                    <Button variant="subtle" size="compact-sm" px={6} onClick={() => choose(r)}>
                      <Plus size={20}/>
                    </Button>
                  }
                  multiline
                >
                  {r.details
                    ? <a href={r.details} target="_blank" rel="noreferrer" style={{color: "inherit", textDecoration: "none"}}>{r.title}</a>
                    : r.title}
                </ListItem>
              ))}
            </ListSection>
            {searchTotal > PAGE_SIZE && (
              <div style={{display: "flex", justifyContent: "center", padding: "8px 0"}}>
                <Pagination
                  total={Math.ceil(searchTotal / PAGE_SIZE)}
                  value={searchPage}
                  onChange={(page) => runSearch(page)}
                  disabled={searching}
                  size="sm"
                />
              </div>
            )}
          </>
        )}
      </div>
      <div>
        <Collapse title={t("add.manual")} className="mb-8">
          <ManualContent
            magnet={magnet}
            onMagnetChange={setMagnet}
            busy={busy}
            fileKey={fileKey}
            textareaRef={textareaRef}
            onSubmitMagnet={submitMagnet}
            onFile={onFile}
          />
        </Collapse>

        <Collapse title={t("settings.categories")}>
          <CategoriesContent
            cats={cats}
            onDelete={(c) => setConfirmDelCat(c)}
            onRename={(c) => {
              setRenameCat(c)
              setCatDialog("rename")
            }}
            onAdd={() => setCatDialog("new")}
          />
        </Collapse>

        <Drawer
          opened={catDialog === "new"}
          onClose={() => setCatDialog(null)}
          title={t("settings.newCategory")}
          position="bottom"
          radius="lg"
          overlayProps={{blur: 2}}
        >
          <Stack gap={8} pb={16} px={4}>
            <TextInput
              autoFocus
              value={newCatName}
              onChange={(e) => setNewCatName(e.target.value)}
              placeholder="Anime"
            />
            <Text size="sm" c="dimmed">{t("settings.libraryType")}</Text>
            <Box style={{display: "flex", flexWrap: "wrap", gap: 8}}>
              {JF_TYPES.map(({key, label, Icon}) => (
                <Button
                  key={key}
                  variant="light"
                  leftSection={<Icon size={16}/>}
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
          onClose={() => {
            setRenameCat(null)
            setCatDialog(null)
          }}
        />

        <Drawer
          opened={!!confirmDelCat}
          onClose={() => setConfirmDelCat(null)}
          title={t("settings.deleteCatTitle")}
          position="bottom"
          radius="lg"
          overlayProps={{blur: 2}}
        >
          <Stack gap={8} pb={16} px={4}>
            <Text size="sm" c="dimmed">{t("settings.deleteCatBody", {name: confirmDelCat?.name})}</Text>
            <Button
              fullWidth
              variant="light"
              leftSection={<Trash2 size={18}/>}
              style={{color: "var(--tg-theme-destructive-text-color)"}}
              onClick={() => confirmDelCat && delCat(confirmDelCat)}
            >
              {t("common.delete")}
            </Button>
            <Button fullWidth variant="light" onClick={() => setConfirmDelCat(null)}>
              {t("common.cancel")}
            </Button>
          </Stack>
        </Drawer>

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
  )
}
