import { useEffect, useState } from "react";
import { Box, Button, Loader, Title } from "@mantine/core";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { speed } from "../format";
import { useToast } from "../components/Toast";
import { ListItem, ListSection } from "../components/ui";

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
      ? <CheckCircle2 size={16} color="var(--tg-theme-link-color)" />
      : <XCircle size={16} color="var(--tg-theme-destructive-text-color)" />
    : <Loader size={16} />;

  return (
    <Box>
      <Box style={{ padding: "16px 16px 4px" }}>
        <Title order={3} style={{ color: "var(--tg-theme-text-color)" }}>
          {t("status.title")}
        </Title>
      </Box>

      <Box p={16} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <ListSection header={t("status.services")}>
          <ListItem after={statusIcon}>qBittorrent</ListItem>
        </ListSection>

        <ListSection header={t("status.transfer")}>
          <ListItem after={st?.connected ? speed(st.dl ?? 0) : "—"}>
            {t("status.download")}
          </ListItem>
          <ListItem after={st?.connected ? speed(st.ul ?? 0) : "—"}>
            {t("status.upload")}
          </ListItem>
        </ListSection>

        <Button
          fullWidth
          variant="light"
          leftSection={<RefreshCw size={18} />}
          onClick={scan}
          disabled={scanning}
        >
          {t("status.scan")}
        </Button>
      </Box>
    </Box>
  );
}
