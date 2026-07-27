import {Button, Drawer} from "@mantine/core"
import {HardDrive, Trash2} from "lucide-react"
import {useTranslation} from "react-i18next"
import type {Torrent} from "@/types"
import s from "./ConfirmDrawers.module.scss"

interface Props {
  confirmDel: Torrent | null
  confirmRemove: Torrent | null
  confirmDelLinks: Torrent | null
  confirmDelBackup: Torrent | null
  onCancelDel: () => void
  onCancelRemove: () => void
  onCancelDelLinks: () => void
  onCancelDelBackup: () => void
  onDelete: (tor: Torrent) => void
  onRemoveFromClient: (tor: Torrent) => void
  onSwitchToRemove: (tor: Torrent) => void
  onDeleteLinks: (tor: Torrent) => void
  onDeleteBackup: (tor: Torrent) => void
}

export function ConfirmDrawers({
  confirmDel, confirmRemove, confirmDelLinks, confirmDelBackup,
  onCancelDel, onCancelRemove, onCancelDelLinks, onCancelDelBackup,
  onDelete, onRemoveFromClient, onSwitchToRemove, onDeleteLinks, onDeleteBackup,
}: Props) {
  const {t} = useTranslation()

  return (
    <>
      <Drawer
        opened={!!confirmDel}
        onClose={onCancelDel}
        title={t("torrents.deleteTitle")}
        position="bottom" radius="lg" overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <div className={s.body}>
          <p className={s.hint}>{t("torrents.deleteBody", {name: confirmDel?.name})}</p>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDel && onDelete(confirmDel)}>
            {confirmDel?.in_qbittorrent ? t("common.delete") : t("torrents.deleteFromDisk")}
          </Button>
          {confirmDel?.in_qbittorrent && (
            <Button fullWidth variant="light" leftSection={<HardDrive size={18}/>}
                    onClick={() => confirmDel && onSwitchToRemove(confirmDel)}>
              {t("torrents.removeFromClient")}
            </Button>
          )}
          <Button fullWidth variant="default" onClick={onCancelDel}>
            {t("common.cancel")}
          </Button>
        </div>
      </Drawer>

      <Drawer
        opened={!!confirmRemove}
        onClose={onCancelRemove}
        title={t("torrents.removeFromClient")}
        position="bottom" radius="lg" overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <div className={s.body}>
          <p className={s.hint}>{t("torrents.removeFromClientBody")}</p>
          <Button fullWidth variant="light" leftSection={<HardDrive size={18}/>}
                  onClick={() => confirmRemove && onRemoveFromClient(confirmRemove)}>
            {t("torrents.removeFromClient")}
          </Button>
          <Button fullWidth variant="default" onClick={onCancelRemove}>
            {t("common.cancel")}
          </Button>
        </div>
      </Drawer>

      <Drawer
        opened={!!confirmDelLinks}
        onClose={onCancelDelLinks}
        title={t("torrents.delLinksTitle")}
        position="bottom" radius="lg" overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <div className={s.body}>
          <p className={s.hint}>{t("torrents.delLinksBody")}</p>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDelLinks && onDeleteLinks(confirmDelLinks)}>
            {t("torrents.delLinks")}
          </Button>
          <Button fullWidth variant="default" onClick={onCancelDelLinks}>
            {t("common.cancel")}
          </Button>
        </div>
      </Drawer>

      <Drawer
        opened={!!confirmDelBackup}
        onClose={onCancelDelBackup}
        title={t("torrents.delBackupTitle")}
        position="bottom" radius="lg" overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <div className={s.body}>
          <p className={s.hint}>{t("torrents.delBackupBody")}</p>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDelBackup && onDeleteBackup(confirmDelBackup)}>
            {t("torrents.delBackup")}
          </Button>
          <Button fullWidth variant="default" onClick={onCancelDelBackup}>
            {t("common.cancel")}
          </Button>
        </div>
      </Drawer>
    </>
  )
}
