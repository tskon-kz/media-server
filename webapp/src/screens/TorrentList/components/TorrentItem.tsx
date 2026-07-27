import {Progress} from "@mantine/core"
import {HardDrive, MoreHorizontal, Wand2} from "lucide-react"
import {useTranslation} from "react-i18next"
import {bytes, pct, speed} from "@/format"
import {TorrentIcon} from "@/icons"
import {ListItem} from "@/components/ui"
import type {Torrent} from "@/types"
import s from "./TorrentItem.module.scss"

interface Props {
  tor: Torrent
  onMenu: (tor: Torrent) => void
}

export function TorrentItem({tor, onMenu}: Props) {
  const {t} = useTranslation()

  return (
    <ListItem
      before={tor.in_qbittorrent
        ? <TorrentIcon state={tor.state}/>
        : <HardDrive size={20} style={{color: "var(--tg-theme-hint-color)"}}/>}
      after={
        <div className={s.actions}>
          <button className={s.btn} onClick={(e) => { e.stopPropagation(); onMenu(tor) }}
                  title={t("torrents.actions")}>
            <MoreHorizontal size={18}/>
          </button>
        </div>
      }
      subtitle={
        <>
          {tor.progress < 1 ? pct(tor.progress) + " · " : ""}
          {tor.size != null ? bytes(tor.size) : t("torrents.sizeUnknown")}
          {tor.dlspeed > 0 ? " · ↓ " + speed(tor.dlspeed) : ""}
          {tor.upscaling && (
            <> · <Wand2 size={12} style={{display: "inline", verticalAlign: "-2px"}}/> {t("torrents.upscaling", {
              done: tor.upscale_done,
              total: tor.upscale_total,
              pct: pct(tor.upscale_progress),
            })}</>
          )}
          {tor.backing_up ? " · 💾 " + t("torrents.backingUp") : ""}
          {tor.restoring ? " · ♻️ " + t("torrents.restoring") : ""}
          {tor.pending_rename > 0 ? " · ✏️ " + t("torrents.pendingRename", {n: tor.pending_rename}) : ""}
        </>
      }
      description={
        tor.progress < 1
          ? <Progress value={tor.progress * 100} size="xs" mt={6}/>
          : tor.upscaling
            ? <Progress value={tor.upscale_progress * 100} size="xs" mt={6} animated/>
            : undefined
      }
      multiline
    >
      {tor.name}
    </ListItem>
  )
}
