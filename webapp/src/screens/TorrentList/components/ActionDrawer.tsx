import {Button, Divider, Drawer, Loader} from "@mantine/core"
import {Clapperboard, Folder, FolderInput, ListChecks, PencilLine, Save, Trash2, Wand2} from "lucide-react"
import {useTranslation} from "react-i18next"
import type {Category, Torrent, Upscaler} from "@/types"
import s from "./ActionDrawer.module.scss"

interface Props {
  tor: Torrent | null
  cats: Category[]
  upscalers: Upscaler[]
  onClose: () => void
  onMove: () => void
  onStructure: (mode: "pretty" | "flat" | "delete") => void
  onResolveNames: () => void
  onUpscale: () => void
  onResults: () => void
  onDelLinks: () => void
  onDelBackup: () => void
  onDelete: () => void
  onBackup: () => void
  onRestoreBackup: () => void
}

export function ActionDrawer({
  tor, cats, upscalers,
  onClose, onMove, onStructure, onResolveNames, onUpscale, onResults,
  onDelLinks, onDelBackup, onDelete, onBackup, onRestoreBackup,
}: Props) {
  const {t} = useTranslation()

  return (
    <Drawer
      opened={!!tor}
      onClose={onClose}
      title={tor?.name ?? t("torrents.actions")}
      position="bottom"
      radius="lg"
      overlayProps={{blur: 2}}
      styles={{title: {width: "100%", textAlign: "center"}}}
    >
      <div className={s.body}>
        {cats.length > 0 && (
          <Button fullWidth variant="default" leftSection={<FolderInput size={18}/>} onClick={onMove}>
            {t("torrents.move")}
          </Button>
        )}
        {tor?.renameable && (
          <>
            <Button fullWidth variant="default" leftSection={<Clapperboard size={18}/>}
                    onClick={() => onStructure("pretty")}>
              {t("torrents.pretty")}
            </Button>
            <Button fullWidth variant="default" leftSection={<Folder size={18}/>}
                    onClick={() => onStructure("flat")}>
              {t("torrents.original")}
            </Button>
            {(tor?.pending_rename ?? 0) > 0 && (
              <Button fullWidth variant="light" color="orange" leftSection={<PencilLine size={18}/>}
                      onClick={onResolveNames}>
                {t("torrents.resolveNames")} ({tor?.pending_rename})
              </Button>
            )}
            <Button fullWidth variant="outline" color="red" leftSection={<Trash2 size={18}/>}
                    onClick={onDelLinks}>
              {t("torrents.delLinks")}
            </Button>
            <Divider my={4}/>
            <Button fullWidth variant="default" leftSection={<Wand2 size={18}/>}
                    disabled={upscalers.length === 0 || tor?.upscaling}
                    onClick={onUpscale}>
              {t("torrents.upscale")}
            </Button>
            {tor?.has_upscale_results && (
              <Button fullWidth variant="default" leftSection={<ListChecks size={18}/>} onClick={onResults}>
                {t("torrents.upscaleResults")}
              </Button>
            )}
          </>
        )}
        {tor?.backing_up ? (
          <Button fullWidth variant="default" leftSection={<Loader size={16}/>} disabled>
            {t("torrents.backingUp")}
          </Button>
        ) : tor?.restoring ? (
          <Button fullWidth variant="default" leftSection={<Loader size={16}/>} disabled>
            {t("torrents.restoring")}
          </Button>
        ) : tor?.has_backup ? (
          <Button fullWidth variant="default" leftSection={<Save size={18}/>} onClick={onRestoreBackup}>
            {t("torrents.restoreBackup")}
          </Button>
        ) : (
          <Button fullWidth variant="default" leftSection={<Save size={18}/>} onClick={onBackup}>
            {t("torrents.backup")}
          </Button>
        )}
        {tor?.has_backup && !tor?.restoring && (
          <Button fullWidth variant="outline" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={onDelBackup}>
            {t("torrents.delBackup")}
          </Button>
        )}
        <Divider my={4}/>
        <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>} onClick={onDelete}>
          {t("common.delete")}
        </Button>
      </div>
    </Drawer>
  )
}
