import {Button} from "@mantine/core"
import {Lock, Unlock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "../../../telegram"
import type {AppConfig, Settings as SettingsData} from "../../../types"
import s from "../Settings.module.scss"

const DEL_COLOR = "var(--tg-theme-destructive-text-color)"

interface JackettContentProps {
  data: SettingsData
  cfg: AppConfig
  onChangePass: () => void
  onRemovePass: () => void
}

export function JackettContent({data, cfg, onChangePass, onRemovePass}: JackettContentProps) {
  const {t} = useTranslation()
  return (
    <>
      <div className={s.infoRow}>
        <div className={s.infoText}>
          <span className={s.infoLabel}>{t("settings.jackett")}</span>
          <span className={s.infoHint}>
            {t("settings.apiKey", {status: t(data.jackett.has_key ? "settings.keyAvailable" : "settings.keyMissing")})}
          </span>
        </div>
        {data.jackett.has_password
          ? <Lock size={16} className={s.infoIcon}/>
          : <Unlock size={16} className={s.infoIcon}/>
        }
      </div>
      <div className={s.buttonStack}>
        <Button fullWidth variant="light" onClick={onChangePass}>{t("settings.changePass")}</Button>
        {data.jackett.has_password && (
          <Button fullWidth variant="light" style={{color: DEL_COLOR}} onClick={onRemovePass}>
            {t("settings.removePass")}
          </Button>
        )}
        {cfg.quick_links && (
          <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jackett)}>
            {t("settings.openWebUI")}
          </Button>
        )}
      </div>
    </>
  )
}
