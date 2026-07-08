import {useState} from "react"
import {Button, Divider, Switch} from "@mantine/core"
import {Lock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "@/telegram"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import {speed} from "@/format"
import type {AppConfig, Settings as SettingsData} from "@/types"
import styles from "../Settings.module.scss"

interface Props {
  data: SettingsData
  cfg: AppConfig
  altSpeedInit: { enabled: boolean; dl: number; ul: number } | null
  onChangePass: () => void
  onGetTemp: () => void
  onRestart: () => void
}

function limitLabel(bytesPerSec: number): string {
  return bytesPerSec === 0 ? "∞" : speed(bytesPerSec)
}

export function QbContent(props: Props) {
  const {t} = useTranslation()
  const [altEnabled, setAltEnabled] = useState<boolean | null>(props.altSpeedInit?.enabled ?? null)
  const [limits, setLimits] = useState(props.altSpeedInit ? { dl: props.altSpeedInit.dl, ul: props.altSpeedInit.ul } : null)
  const [toggling, setToggling] = useState(false)

  const toggleAltSpeed = async () => {
    if (toggling) return
    setToggling(true)
    try {
      const result = await api.toggleAltSpeed()
      setAltEnabled(result.alt_speed_enabled)
      const st = await api.status()
      if (st.connected) setLimits({ dl: st.dl_rate_limit ?? 0, ul: st.up_rate_limit ?? 0 })
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setToggling(false)
    }
  }

  return (
    <>
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.credentials")}</span>
          <span className={styles.infoHint}>{t("settings.userSub", {user: props.data.qbittorrent.user})}</span>
        </div>
        {props.data.qbittorrent.is_perm && <Lock size={16} className={styles.infoIcon}/>}
      </div>
      {altEnabled !== null && (
        <>
          <Divider/>
          <div className={styles.infoRow}>
            <div className={styles.infoText}>
              <span className={styles.infoLabel}>{t("status.altSpeed")}</span>
              {limits && (
                <span className={styles.infoHint}>
                  ↓ {limitLabel(limits.dl)} · ↑ {limitLabel(limits.ul)}
                </span>
              )}
            </div>
            <Switch
              checked={altEnabled}
              disabled={toggling}
              onChange={toggleAltSpeed}
              label={altEnabled ? t("status.altSpeedOn") : t("status.altSpeedOff")}
            />
          </div>
        </>
      )}
      <div className={styles.buttonStack}>
        <Button fullWidth variant="dark" onClick={props.onChangePass}>{t("settings.changePass")}</Button>
        {!props.data.qbittorrent.is_perm && (
          <Button fullWidth variant="dark" onClick={props.onGetTemp}>{t("settings.getTemp")}</Button>
        )}
        <Button fullWidth variant="filled" color="red" onClick={props.onRestart}>{t("settings.restart")}</Button>
        {props.cfg.quick_links && (
          <Button fullWidth variant="default" onClick={() => openExternal(props.cfg.quick_links!.qbittorrent)}>
            {t("settings.openWebUI")}
          </Button>
        )}
      </div>
    </>
  )
}
