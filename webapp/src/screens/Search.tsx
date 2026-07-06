import { useState, useEffect } from "react";
import { Button, Cell, Input, List, Placeholder, Section, Spinner, Title } from "@telegram-apps/telegram-ui";
import { Search as SearchIcon } from "lucide-react";
import { api } from "../api";
import { bytes } from "../format";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import type { Category, SearchResult } from "../types";

export function Search() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [cats, setCats] = useState<Category[]>([]);
  const [pick, setPick] = useState<SearchResult | null>(null);

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}); }, []);

  const run = async () => {
    const query = q.trim();
    if (!query) return;
    setLoading(true);
    try {
      const r = await api.search(query);
      setResults(r.results);
    } catch (e) {
      toast((e as Error).message, "err");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const choose = (r: SearchResult) => {
    if (cats.length === 0) addNow(r);
    else setPick(r);
  };

  const addNow = async (r: SearchResult, cat?: Category) => {
    setPick(null);
    try { await api.searchAdd(r, cat?.id); toast("Added"); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <div>
      <div style={{ padding: "16px 16px 4px" }}>
        <Title>Search</Title>
      </div>
      <List>
        <Section>
          <Input
            header="Search Jackett"
            placeholder="Search Jackett…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            after={
              <Button mode="plain" size="s" onClick={run} disabled={loading || !q.trim()}>
                <SearchIcon size={20} />
              </Button>
            }
          />
        </Section>

        {loading && <Spinner size="m" style={{ display: "block", margin: "24px auto" }} />}

        {results !== null && !loading && results.length === 0 && (
          <Placeholder header="No results" description="Try a different query" />
        )}

        {results && results.length > 0 && (
          <Section>
            {results.map((r, i) => (
              <Cell
                key={i}
                subtitle={`${r.seeders} seeders · ${bytes(r.size)} · ${r.tracker}${r.date ? " · " + r.date.slice(0, 10) : ""}`}
                onClick={() => choose(r)}
                multiline
              >
                {r.title}
              </Cell>
            ))}
          </Section>
        )}
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
