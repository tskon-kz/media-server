import {Button} from "@mantine/core"
import {RefreshCw, Users} from "lucide-react"
import {useTranslation} from "react-i18next"
import {openExternal} from "@/telegram"
import type {AppConfig} from "@/types"
import styles from "../Settings.module.scss"

interface JellyfinContentProps {
  cfg: AppConfig
  scanning: boolean
  onScan: () => void
  onManageUsers: () => void
}

export function JellyfinContent({cfg, scanning, onScan, onManageUsers}: JellyfinContentProps) {
  const {t} = useTranslation()
  return (
    <div className={styles.buttonStack}>
      <Button fullWidth variant="light" leftSection={<RefreshCw size={18}/>} onClick={onScan} disabled={scanning}>
        {t("settings.scanLibrary")}
      </Button>
      <Button fullWidth variant="light" leftSection={<Users size={18}/>} onClick={onManageUsers}>
        {t("settings.manageUsers")}
      </Button>
      {cfg.quick_links && (
        <Button fullWidth variant="light" onClick={() => openExternal(cfg.quick_links!.jellyfin)}>
          {t("settings.openWebUI")}
        </Button>
      )}
    </div>
  )
}
