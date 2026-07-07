import {useState} from "react"
import {Button, Drawer, Loader} from "@mantine/core"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import type {UpdateInfo} from "@/types"
import styles from "../Settings.module.scss"

interface Props {
  info: UpdateInfo
  onDone: () => void
}

export function UpdateContent({info, onDone}: Props) {
  const {t} = useTranslation()
  const [updating, setUpdating] = useState(false)
  const [confirmEdge, setConfirmEdge] = useState(false)

  const trigger = async (tag: "stable" | "edge") => {
    setUpdating(true)
    setConfirmEdge(false)
    try {
      await api.triggerUpdate(tag)
      toast(t("settings.updateStarted"), "ok")
      onDone()
    } catch (e) {
      toast((e as Error).message, "err")
      setUpdating(false)
    }
  }

  return (
    <>
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.updateVersion")}</span>
          <span className={styles.infoHint}>{info.current}</span>
        </div>
      </div>
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.updateChannel")}</span>
          <span className={styles.infoHint}>
            {info.channel === "edge" ? t("settings.updateEdge") : t("settings.updateStable")}
          </span>
        </div>
      </div>
      {info.has_update && (
        <div className={styles.infoRow}>
          <div className={styles.infoText}>
            <span className={styles.infoLabel}>{t("settings.updateAvailable")}</span>
            <span className={styles.infoHint}>{info.latest}</span>
          </div>
        </div>
      )}
      <div className={styles.buttonStack}>
        {info.has_update && (
          <Button fullWidth variant="filled" disabled={updating} onClick={() => trigger("stable")}>
            {updating ? <Loader size="xs" color="white"/> : t("settings.updateBtn", {version: info.latest})}
          </Button>
        )}
        {info.channel === "edge" ? (
          <Button fullWidth variant="dark" disabled={updating} onClick={() => trigger("stable")}>
            {t("settings.updateSwitchToStable")}
          </Button>
        ) : (
          <Button fullWidth variant="dark" disabled={updating} onClick={() => setConfirmEdge(true)}>
            {t("settings.updateSwitchToEdge")}
          </Button>
        )}
      </div>

      <Drawer
        opened={confirmEdge}
        onClose={() => setConfirmEdge(false)}
        title={t("settings.updateSwitchToEdge")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <div style={{padding: "0 4px 16px", display: "flex", flexDirection: "column", gap: 8}}>
          <p style={{margin: "0 0 4px", fontSize: 14, color: "var(--tg-theme-hint-color)"}}>
            {t("settings.updateEdgeWarning")}
          </p>
          <Button fullWidth variant="filled" color="orange" onClick={() => trigger("edge")}>
            {t("settings.updateConfirmEdge")}
          </Button>
          <Button fullWidth variant="default" onClick={() => setConfirmEdge(false)}>
            {t("common.cancel")}
          </Button>
        </div>
      </Drawer>
    </>
  )
}
