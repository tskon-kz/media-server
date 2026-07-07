import {Button} from "@mantine/core"
import {Lock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "../../../telegram"
import type {AppConfig, Settings as SettingsData} from "../../../types"
import s from "../Settings.module.scss"

interface QbContentProps {
  data: SettingsData
  cfg: AppConfig
  onChangePass: () => void
  onGetTemp: () => void
  onRestart: () => void
}

export function QbContent({data, cfg, onChangePass, onGetTemp, onRestart}: QbContentProps) {
  const {t} = useTranslation()
  return (
    <>
      <div className={s.infoRow}>
        <div className={s.infoText}>
          <span className={s.infoLabel}>{t("settings.credentials")}</span>
          <span className={s.infoHint}>{t("settings.userSub", {user: data.qbittorrent.user})}</span>
        </div>
        {data.qbittorrent.is_perm && <Lock size={16} className={s.infoIcon}/>}
      </div>
      <div className={s.buttonStack}>
        <Button fullWidth variant="light" onClick={onChangePass}>{t("settings.changePass")}</Button>
        {!data.qbittorrent.is_perm && (
          <Button fullWidth variant="light" onClick={onGetTemp}>{t("settings.getTemp")}</Button>
        )}
        <Button fullWidth variant="light" onClick={onRestart}>{t("settings.restart")}</Button>
        {cfg.quick_links && (
          <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.qbittorrent)}>
            {t("settings.openWebUI")}
          </Button>
        )}
      </div>
    </>
  )
}
