import {useCallback, useEffect, useRef, useState} from "react"
import {Box, Button, Divider, Drawer, Loader, Progress, Stack, Title} from "@mantine/core"
import {Clapperboard, Folder, FolderInput, HardDrive, Layers, RefreshCw, Save, Trash2, Wand2} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes, pct, speed} from "@/format"
import {haptic} from "@/telegram"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {TorrentIcon} from "@/icons"
import {ListItem, ListPlaceholder, ListSection} from "@/components/ui"
import type {Category, Torrent, Upscaler} from "@/types"
import s from "./TorrentList.module.scss"

export function TorrentList() {
  const {t} = useTranslation()
  const [torrents, setTorrents] = useState<Torrent[] | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [moving, setMoving] = useState<Torrent | null>(null)
  const [structFor, setStructFor] = useState<Torrent | null>(null)
  const [upscaleFor, setUpscaleFor] = useState<Torrent | null>(null)
  const [upscalers, setUpscalers] = useState<Upscaler[]>([])
  const [confirmDel, setConfirmDel] = useState<Torrent | null>(null)
  const [pull, setPull] = useState(0)
  const [confirmRemove, setConfirmRemove] = useState<Torrent | null>(null)

  const load = useCallback(async () => {
    try {
      const [tr, c] = await Promise.all([api.torrents(), api.categories()])
      setTorrents(tr.torrents)
      setCats(c.categories)
    } catch (e) {
      toast((e as Error).message, "err")
      setTorrents([])
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    api.config().then((c) => setUpscalers(c.upscalers ?? [])).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(load, 5000)
    return () => clearInterval(iv)
  }, [load])

  const startY = useRef<number | null>(null)
  const onTouchStart = (e: React.TouchEvent) => {
    if (window.scrollY <= 0) startY.current = e.touches[0].clientY
  }
  const onTouchMove = (e: React.TouchEvent) => {
    if (startY.current === null) return
    const d = e.touches[0].clientY - startY.current
    if (d > 0) setPull(Math.min(d, 80))
  }
  const onTouchEnd = () => {
    if (pull > 55) {
      haptic("light");
      load()
    }
    setPull(0)
    startY.current = null
  }

  const doDelete = async (tor: Torrent) => {
    setConfirmDel(null)
    try {
      if (tor.in_qbittorrent && tor.hash) {
        await api.deleteTorrent(tor.hash)
      } else {
        await api.deleteDiskEntry(tor.disk_id)
      }
      toast(t("torrents.deleted"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doRemoveFromClient = async (tor: Torrent) => {
    setConfirmRemove(null)
    try {
      await api.removeFromClient(tor.hash!)
      toast(t("torrents.removedFromClient"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doMove = async (tor: Torrent, cat: Category) => {
    setMoving(null)
    try {
      await api.moveTorrent(tor.disk_id, cat.id)
      toast(t("torrents.moved", {name: cat.name}))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doStructure = async (tor: Torrent, mode: "pretty" | "flat" | "delete") => {
    setStructFor(null)
    try {
      const r = await api.structure(tor.disk_id, mode)
      if (r.xdev) toast(t("torrents.xdev"), "err")
      else if (mode === "pretty") toast(t("torrents.linked", {n: r.linked, pending: r.pending}))
      else toast(t("common.done"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doUpscale = async (tor: Torrent, upscalerId: string) => {
    setUpscaleFor(null)
    setStructFor(null)
    try {
      const r = await api.upscale(tor.disk_id, upscalerId)
      toast(t("torrents.upscaleQueued", {n: r.queued}))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doBackup = async (tor: Torrent) => {
    setStructFor(null)
    try {
      await api.backup(tor.disk_id)
      toast(t("torrents.backupSaved"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doRestoreBackup = async (tor: Torrent) => {
    setStructFor(null)
    try {
      await api.restoreBackup(tor.disk_id)
      toast(t("torrents.backupRestored"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doDeleteBackup = async (tor: Torrent) => {
    setStructFor(null)
    try {
      await api.deleteBackup(tor.disk_id)
      toast(t("torrents.backupDeleted"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  if (torrents === null) {
    return (
      <Box style={{textAlign: "center", paddingTop: 60}}>
        <Loader size="md"/>
      </Box>
    )
  }

  return (
    <Box onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <Box style={{display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 16px 4px"}}
           className="mb-16">
        <Title order={3} style={{color: "var(--tg-theme-text-color)", fontSize: 20}}>
          {t("torrents.title")}
        </Title>
        <Button variant="subtle" px={8} onClick={load}>
          <RefreshCw size={20}/>
        </Button>
      </Box>

      {pull > 0 && (
        <Box style={{textAlign: "center", height: pull, color: "var(--tg-theme-hint-color)", fontSize: 14}}>
          {t("torrents.pull")}
        </Box>
      )}

      <Box px={16}>
        {torrents.length === 0 ? (
          <ListPlaceholder header={t("torrents.empty")} description={t("torrents.emptyHint")}/>
        ) : (
          <ListSection>
            {torrents.map((tor) => (
              <ListItem
                key={tor.disk_id}
                before={tor.in_qbittorrent ? <TorrentIcon state={tor.state}/> : <HardDrive size={20} style={{color: "var(--tg-theme-hint-color)"}}/>}
                after={
                  <div className={s.iconActions}>
                    {cats.length > 0 && (
                      <button
                        className={s.iconBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          setMoving(tor)
                        }}
                        title={t("torrents.move")}
                      >
                        <FolderInput size={18}/>
                      </button>
                    )}
                    {tor.renameable && (
                      <button
                        className={s.iconBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          setStructFor(tor)
                        }}
                        title={t("torrents.structure")}
                      >
                        <Layers size={18}/>
                      </button>
                    )}
                    <button
                      className={`${s.iconBtn} ${s.danger}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDel(tor)
                      }}
                      title={t("common.delete")}
                    >
                      <Trash2 size={18}/>
                    </button>
                  </div>
                }
                subtitle={`${tor.progress < 1 ? pct(tor.progress) + " · " : ""}${tor.size != null ? bytes(tor.size) : t("torrents.sizeUnknown")}${tor.dlspeed > 0 ? " · ↓ " + speed(tor.dlspeed) : ""}${tor.upscaling ? " · ✨ " + t("torrents.upscaling", {pct: pct(tor.upscale_progress)}) : ""}`}
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
            ))}
          </ListSection>
        )}
      </Box>

      <Drawer
        opened={!!confirmDel}
        onClose={() => setConfirmDel(null)}
        title={t("torrents.deleteTitle")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.deleteBody", {name: confirmDel?.name})}
          </Box>
          <Button fullWidth variant="filled" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDel && doDelete(confirmDel)}>
            {confirmDel?.in_qbittorrent ? t("common.delete") : t("torrents.deleteFromDisk")}
          </Button>
          {confirmDel?.in_qbittorrent && (
            <Button fullWidth variant="filled" color="orange" leftSection={<HardDrive size={18}/>}
                    onClick={() => {
                      const tor = confirmDel
                      setConfirmDel(null)
                      setConfirmRemove(tor)
                    }}>
              {t("torrents.removeFromClient")}
            </Button>
          )}
          <Button fullWidth variant="default" onClick={() => setConfirmDel(null)}>
            {t("common.cancel")}
          </Button>
        </Stack>
      </Drawer>

      <Drawer
        opened={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        title={t("torrents.removeFromClient")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.removeFromClientBody")}
          </Box>
          <Button fullWidth variant="filled" color="orange" leftSection={<HardDrive size={18}/>}
                  onClick={() => confirmRemove && doRemoveFromClient(confirmRemove)}>
            {t("torrents.removeFromClient")}
          </Button>
          <Button fullWidth variant="default" onClick={() => setConfirmRemove(null)}>
            {t("common.cancel")}
          </Button>
        </Stack>
      </Drawer>

      <CategoryPicker
        categories={cats}
        open={!!moving}
        title={t("torrents.move")}
        onPick={(c) => moving && doMove(moving, c)}
        onClose={() => setMoving(null)}
      />

      <Drawer
        opened={!!structFor}
        onClose={() => setStructFor(null)}
        title={t("torrents.structure")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Button fullWidth variant="dark" leftSection={<Clapperboard size={18}/>}
                  onClick={() => structFor && doStructure(structFor, "pretty")}>
            {t("torrents.pretty")}
          </Button>
          <Button fullWidth variant="dark" leftSection={<Folder size={18}/>}
                  onClick={() => structFor && doStructure(structFor, "flat")}>
            {t("torrents.original")}
          </Button>
          <Button fullWidth variant="filled" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => structFor && doStructure(structFor, "delete")}>
            {t("torrents.delLinks")}
          </Button>
          <Divider my={4}/>
          <Button fullWidth variant="light" leftSection={<Wand2 size={18}/>}
                  disabled={upscalers.length === 0 || !!structFor?.upscaling}
                  onClick={() => setUpscaleFor(structFor)}>
            {t("torrents.upscale")}
          </Button>
          {structFor?.has_backup ? (
            <Button fullWidth variant="light" color="teal" leftSection={<Save size={18}/>}
                    onClick={() => structFor && doRestoreBackup(structFor)}>
              {t("torrents.restoreBackup")}
            </Button>
          ) : (
            <Button fullWidth variant="default" leftSection={<Save size={18}/>}
                    onClick={() => structFor && doBackup(structFor)}>
              {t("torrents.backup")}
            </Button>
          )}
          {structFor?.has_backup && (
            <Button fullWidth variant="subtle" color="red" leftSection={<Trash2 size={18}/>}
                    onClick={() => structFor && doDeleteBackup(structFor)}>
              {t("torrents.delBackup")}
            </Button>
          )}
        </Stack>
      </Drawer>

      <Drawer
        opened={!!upscaleFor}
        onClose={() => setUpscaleFor(null)}
        title={t("torrents.upscalePick")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <Stack gap={8} pb={16} px={4}>
          {upscalers.map((u) => (
            <Button key={u.id} fullWidth variant="dark" leftSection={<Wand2 size={18}/>}
                    onClick={() => upscaleFor && doUpscale(upscaleFor, u.id)}>
              {u.label}{u.needs_gpu ? ` · ${t("torrents.gpuHint")}` : ""}
            </Button>
          ))}
        </Stack>
      </Drawer>
    </Box>
  )
}
