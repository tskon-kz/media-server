import {Button, Divider, Switch} from "@mantine/core"
import {Lock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "@/telegram"
import {speed} from "@/format"
import type {AppConfig, Settings as SettingsData} from "@/types"
import styles from "../Settings.module.scss"

interface Props {
  data: SettingsData
  cfg: AppConfig
  altSpeedEnabled: boolean | null
  altSpeedLimits: { dl: number; ul: number } | null
  togglingAltSpeed: boolean
  onChangePass: () => void
  onGetTemp: () => void
  onRestart: () => void
  onToggleAltSpeed: () => void
}

function limitLabel(bytesPerSec: number): string {
  return bytesPerSec === 0 ? "∞" : speed(bytesPerSec)
}

export function QbContent(props: Props) {
  const {t} = useTranslation()
  return (
    <>
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.credentials")}</span>
          <span className={styles.infoHint}>{t("settings.userSub", {user: props.data.qbittorrent.user})}</span>
        </div>
        {props.data.qbittorrent.is_perm && <Lock size={16} className={styles.infoIcon}/>}
      </div>
      {props.altSpeedEnabled !== null && (
        <>
          <Divider/>
          <div className={styles.infoRow}>
            <div className={styles.infoText}>
              <span className={styles.infoLabel}>{t("status.altSpeed")}</span>
              {props.altSpeedLimits && (
                <span className={styles.infoHint}>
                  ↓ {limitLabel(props.altSpeedLimits.dl)} · ↑ {limitLabel(props.altSpeedLimits.ul)}
                </span>
              )}
            </div>
            <Switch
              checked={props.altSpeedEnabled}
              disabled={props.togglingAltSpeed}
              onChange={props.onToggleAltSpeed}
              label={props.altSpeedEnabled ? t("status.altSpeedOn") : t("status.altSpeedOff")}
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
