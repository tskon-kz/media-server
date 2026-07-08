import {Button, Divider, Switch} from "@mantine/core"
import {Lock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "@/telegram"
import type {AppConfig, Settings as SettingsData} from "@/types"
import styles from "../Settings.module.scss"

interface QbContentProps {
  data: SettingsData
  cfg: AppConfig
  altSpeedEnabled: boolean | null
  togglingAltSpeed: boolean
  onChangePass: () => void
  onGetTemp: () => void
  onRestart: () => void
  onToggleAltSpeed: () => void
}

export function QbContent({data, cfg, altSpeedEnabled, togglingAltSpeed, onChangePass, onGetTemp, onRestart, onToggleAltSpeed}: QbContentProps) {
  const {t} = useTranslation()
  return (
    <>
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.credentials")}</span>
          <span className={styles.infoHint}>{t("settings.userSub", {user: data.qbittorrent.user})}</span>
        </div>
        {data.qbittorrent.is_perm && <Lock size={16} className={styles.infoIcon}/>}
      </div>
      {altSpeedEnabled !== null && (
        <>
          <Divider/>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{t("status.altSpeed")}</span>
            <Switch
              checked={altSpeedEnabled}
              disabled={togglingAltSpeed}
              onChange={onToggleAltSpeed}
              label={altSpeedEnabled ? t("status.altSpeedOn") : t("status.altSpeedOff")}
            />
          </div>
        </>
      )}
      <div className={styles.buttonStack}>
        <Button fullWidth variant="dark" onClick={onChangePass}>{t("settings.changePass")}</Button>
        {!data.qbittorrent.is_perm && (
          <Button fullWidth variant="dark" onClick={onGetTemp}>{t("settings.getTemp")}</Button>
        )}
        <Button fullWidth variant="filled" color="red" onClick={onRestart}>{t("settings.restart")}</Button>
        {cfg.quick_links && (
          <Button fullWidth variant="default" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>
            {t("settings.openWebUI")}
          </Button>
        )}
      </div>
    </>
  )
}
