import {Button} from "@mantine/core"
import {Lock, Unlock} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "@/telegram"
import type {AppConfig, Settings as SettingsData} from "@/types"
import styles from "../Settings.module.scss"

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
      <div className={styles.infoRow}>
        <div className={styles.infoText}>
          <span className={styles.infoLabel}>{t("settings.jackett")}</span>
          <span className={styles.infoHint}>
            {t("settings.apiKey", {status: t(data.jackett.has_key ? "settings.keyAvailable" : "settings.keyMissing")})}
          </span>
        </div>
        {data.jackett.has_password
          ? <Lock size={16} className={styles.infoIcon}/>
          : <Unlock size={16} className={styles.infoIcon}/>
        }
      </div>
      <div className={styles.buttonStack}>
        <Button fullWidth variant="dark" onClick={onChangePass}>{t("settings.changePass")}</Button>
        {data.jackett.has_password && (
          <Button fullWidth variant="filled" color="red" onClick={onRemovePass}>
            {t("settings.removePass")}
          </Button>
        )}
        {cfg.quick_links && (
          <Button fullWidth variant="default" onClick={() => openExternal(cfg.quick_links!.jackett)}>
            {t("settings.openWebUI")}
          </Button>
        )}
      </div>
    </>
  )
}
