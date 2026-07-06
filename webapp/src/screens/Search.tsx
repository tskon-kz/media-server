import { useEffect, useState } from "react";
import { api } from "../api";
import { bytes } from "../format";
import { openExternal } from "../telegram";
import { useToast } from "../components/Toast";
import { CategoryPicker } from "../components/CategoryPicker";
import type { Category, SearchResult } from "../types";
import s from "./Search.module.scss";

export function Search() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [pick, setPick] = useState<SearchResult | null>(null);

  useEffect(() => { api.categories().then((c) => setCats(c.categories)).catch(() => {}); }, []);

  const run = async () => {
    const query = q.trim();
    if (!query) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await api.search(query);
      setResults(r.results);
    } catch (e) {
      setErr((e as Error).message);
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
    try {
      await api.searchAdd(r, cat?.id);
      toast("✅ Added");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div>
      <div className={s.screenTitle}>Search</div>

      <div className={s.card}>
        <div className={s.row}>
          <input
            className={s.grow}
            style={{ marginBottom: 0 }}
            placeholder="Search Jackett…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
          <button onClick={run} disabled={loading || !q.trim()}>Go</button>
        </div>
      </div>

      {loading && <div className={s.spinner} />}
      {err && <div className={`${s.card} ${s.errorText}`}>{err}</div>}
      {results !== null && !loading && results.length === 0 && !err && (
        <div className={s.centerMsg}>🔍 No results</div>
      )}

      {results?.map((r, i) => (
        <div key={i} className={`${s.card} ${s.tappable}`} onClick={() => choose(r)}>
          <div className={s.titleText} style={{ whiteSpace: "normal" }}>{r.title}</div>
          <div className={s.subtitle}>
            🌱 {r.seeders} · 📦 {bytes(r.size)} ·{" "}
            {r.details ? (
              <a onClick={(e) => { e.stopPropagation(); openExternal(r.details); }}>{r.tracker}</a>
            ) : r.tracker}
            {r.date ? ` · ${r.date.slice(0, 10)}` : ""}
          </div>
        </div>
      ))}

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
