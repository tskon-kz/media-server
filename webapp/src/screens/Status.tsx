import { useEffect, useState } from "react";
import { Button, Cell, List, Section, Spinner, Title } from "@telegram-apps/telegram-ui";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { speed } from "../format";
import { useToast } from "../components/Toast";

export function Status() {
  const toast = useToast();
  const { t } = useTranslation();
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
      toast(r.ok ? t("status.scanOk") : t("status.scanFail"), r.ok ? "ok" : "err");
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setScanning(false);
    }
  };

  const statusIcon = st
    ? st.connected
      ? <CheckCircle2 size={16} color="var(--tgui--accent_text_color)" />
      : <XCircle size={16} color="var(--tgui--destructive_text_color)" />
    : <Spinner size="s" />;

  return (
    <div>
      <div style={{ padding: "16px 16px 4px" }}>
        <Title>{t("status.title")}</Title>
      </div>
      <List>
        <Section header={t("status.services")}>
          <Cell after={statusIcon}>qBittorrent</Cell>
        </Section>

        <Section header={t("status.transfer")}>
          <Cell after={st?.connected ? speed(st.dl ?? 0) : "—"}>{t("status.download")}</Cell>
          <Cell after={st?.connected ? speed(st.ul ?? 0) : "—"}>{t("status.upload")}</Cell>
        </Section>
      </List>

      <div style={{ padding: "0 16px" }}>
        <Button stretched mode="bezeled" before={<RefreshCw size={18} />} onClick={scan} disabled={scanning}>
          {t("status.scan")}
        </Button>
      </div>
    </div>
  );
}
