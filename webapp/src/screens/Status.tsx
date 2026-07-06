import { useEffect, useState } from "react";
import { api } from "../api";
import { speed } from "../format";
import { useToast } from "../components/Toast";
import s from "./Status.module.scss";

export function Status() {
  const toast = useToast();
  const [st, setSt] = useState<{ connected: boolean; dl?: number; ul?: number } | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    const load = () => api.status().then(setSt).catch(() => setSt({ connected: false }));
    load();
    const iv = setInterval(load, 2000);
    return () => clearInterval(iv);
  }, []);

  const scan = async () => {
    setScanning(true);
    try {
      const r = await api.scan();
      toast(r.ok ? "🔄 Jellyfin scan started" : "Scan failed", r.ok ? "ok" : "err");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div>
      <div className={s.screenTitle}>Status</div>

      <div className={s.card}>
        <div className={`${s.row} ${s.spread}`}>
          <span className={s.hint}>qBittorrent</span>
          <span>{st ? (st.connected ? "✅ connected" : "❌ unavailable") : "…"}</span>
        </div>
      </div>

      <div className={s.row} style={{ gap: 10 }}>
        <div className={`${s.card} ${s.grow}`} style={{ textAlign: "center" }}>
          <div className={s.hint}>Download</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
            ↓ {st?.connected ? speed(st.dl ?? 0) : "—"}
          </div>
        </div>
        <div className={`${s.card} ${s.grow}`} style={{ textAlign: "center" }}>
          <div className={s.hint}>Upload</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
            ↑ {st?.connected ? speed(st.ul ?? 0) : "—"}
          </div>
        </div>
      </div>

      <button className="full secondary" style={{ marginTop: 10 }} onClick={scan} disabled={scanning}>
        🔄 Scan Jellyfin library
      </button>
    </div>
  );
}
