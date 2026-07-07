import {useState, useEffect} from "react"
import {Box, Button, Loader, Stack, TextInput, Title} from "@mantine/core"
import {Plus, Search as SearchIcon} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes} from "@/format"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {ListItem, ListPlaceholder, ListSection} from "@/components/ui"
import type {Category, SearchResult} from "@/types"

export function Search() {
  const {t} = useTranslation()
  const [q, setQ] = useState("")
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [cats, setCats] = useState<Category[]>([])
  const [pick, setPick] = useState<SearchResult | null>(null)

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}) }, [])

  const run = async () => {
    const query = q.trim()
    if (!query) return
    setLoading(true)
    try {
      const r = await api.search(query)
      setResults(r.results)
    } catch (e) {
      toast((e as Error).message, "err")
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const choose = (r: SearchResult) => {
    if (cats.length === 0) addNow(r)
    else setPick(r)
  }

  const addNow = async (r: SearchResult, cat?: Category) => {
    setPick(null)
    try { await api.searchAdd(r, cat?.id); toast(t("common.added")) }
    catch (e) { toast((e as Error).message, "err") }
  }

  return (
    <Box>
      <Box style={{padding: "16px 16px 4px"}}>
        <Title order={3} style={{color: "var(--tg-theme-text-color)"}}>
          {t("search.title")}
        </Title>
      </Box>

      <Box p={16}>
        <Stack gap={8}>
          <TextInput
            placeholder={t("search.placeholder")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            rightSection={
              <Button
                variant="subtle"
                size="compact-sm"
                px={4}
                onClick={run}
                disabled={loading || !q.trim()}
              >
                <SearchIcon size={18}/>
              </Button>
            }
            rightSectionWidth={40}
          />

          {loading && (
            <Box style={{textAlign: "center", padding: "24px 0"}}>
              <Loader size="md"/>
            </Box>
          )}

          {results !== null && !loading && results.length === 0 && (
            <ListPlaceholder header={t("search.empty")} description={t("search.emptyHint")}/>
          )}

          {results && results.length > 0 && (
            <ListSection>
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
          )}
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
  )
}
