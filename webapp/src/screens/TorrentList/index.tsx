import {useCallback, useEffect, useRef, useState} from "react"
import {Button, Loader} from "@mantine/core"
import {ChevronLeft, ChevronRight, Pause, Play, RefreshCw, Wand2, XCircle} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {haptic} from "@/telegram"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {ListPlaceholder, ListSection} from "@/components/ui"
import type {Category, CompressionLevel, Torrent, Upscaler, UpscaleTarget} from "@/types"
import {ActionDrawer} from "./components/ActionDrawer"
import {TorrentItem} from "./components/TorrentItem"
import {ConfirmDrawers} from "./components/ConfirmDrawers"
import {UpscaleDrawer} from "./components/UpscaleDrawer"
import {UpscaleResultsDrawer} from "./components/UpscaleResultsDrawer"
import {RenameJobsDrawer} from "./components/RenameJobsDrawer"
import s from "./TorrentList.module.scss"

const PAGE_SIZE = 10

export function TorrentList() {
  const {t} = useTranslation()
  const [torrents, setTorrents] = useState<Torrent[] | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [upscalers, setUpscalers] = useState<Upscaler[]>([])
  const [compressionLevels, setCompressionLevels] = useState<CompressionLevel[]>([])
  const [upscaleTargets, setUpscaleTargets] = useState<UpscaleTarget[]>([])
  const [upscaleTarget, setUpscaleTarget] = useState("2x")
  const [paused, setPaused] = useState(false)
  const [pull, setPull] = useState(0)
  const [catPages, setCatPages] = useState<Record<string, number>>({})

  // drawer state
  const [menuFor, setMenuFor] = useState<Torrent | null>(null)
  const [upscaleFor, setUpscaleFor] = useState<Torrent | null>(null)
  const [resultsFor, setResultsFor] = useState<Torrent | null>(null)
  const [renameFor, setRenameFor] = useState<Torrent | null>(null)
  const [moving, setMoving] = useState<Torrent | null>(null)
  const [confirmDel, setConfirmDel] = useState<Torrent | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<Torrent | null>(null)
  const [confirmDelLinks, setConfirmDelLinks] = useState<Torrent | null>(null)
  const [confirmDelBackup, setConfirmDelBackup] = useState<Torrent | null>(null)

  // track in-flight backup/restore to toast on completion
  const backingUp = useRef<Set<string>>(new Set())
  const restoring = useRef<Set<string>>(new Set())

  const load = useCallback(async () => {
    try {
      const [tr, c] = await Promise.all([api.torrents(), api.categories()])
      for (const tor of tr.torrents) {
        if (tor.backing_up) backingUp.current.add(tor.disk_id)
        else if (backingUp.current.has(tor.disk_id)) {
          backingUp.current.delete(tor.disk_id)
          toast(tor.has_backup ? t("torrents.backupSaved") : t("torrents.backupFailed"),
            tor.has_backup ? "ok" : "err")
        }
        if (tor.restoring) restoring.current.add(tor.disk_id)
        else if (restoring.current.has(tor.disk_id)) {
          restoring.current.delete(tor.disk_id)
          toast(t("torrents.backupRestored"), "ok")
        }
      }
      setTorrents(tr.torrents)
      setCats(c.categories)
    } catch (e) {
      toast((e as Error).message, "err")
      setTorrents([])
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    api.config().then((c) => {
      setUpscalers(c.upscalers ?? [])
      setCompressionLevels(c.compression_levels ?? [])
      setUpscaleTargets(c.upscale_targets ?? [])
      setUpscaleTarget(c.upscale_target ?? "2x")
      setPaused(c.upscale_paused)
    }).catch(() => {})
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
    if (pull > 55) { haptic("light"); load() }
    setPull(0)
    startY.current = null
  }

  const doDelete = async (tor: Torrent) => {
    setConfirmDel(null)
    try {
      if (tor.in_qbittorrent && tor.hash) await api.deleteTorrent(tor.hash)
      else await api.deleteDiskEntry(tor.disk_id)
      toast(t("torrents.deleted"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doRemoveFromClient = async (tor: Torrent) => {
    setConfirmRemove(null)
    try {
      await api.removeFromClient(tor.hash!)
      toast(t("torrents.removedFromClient"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doMove = async (tor: Torrent, cat: Category) => {
    setMoving(null)
    try {
      await api.moveTorrent(tor.disk_id, cat.id)
      toast(t("torrents.moved", {name: cat.name}))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doStructure = async (mode: "pretty" | "flat" | "delete") => {
    const tor = menuFor
    setMenuFor(null)
    if (!tor) return
    try {
      const r = await api.structure(tor.disk_id, mode)
      if (r.xdev) toast(t("torrents.xdev"), "err")
      else if (mode === "pretty") {
        if (r.pending && r.pending > 0) {
          toast(t("torrents.linked", {n: r.linked, pending: r.pending}))
          setRenameFor(tor)
        } else toast(t("common.done"))
      } else toast(t("common.done"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doDeleteLinks = async (tor: Torrent) => {
    setConfirmDelLinks(null)
    try {
      await api.structure(tor.disk_id, "delete")
      toast(t("common.done"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doBackup = async () => {
    const tor = menuFor
    setMenuFor(null)
    if (!tor) return
    try {
      await api.backup(tor.disk_id)
      backingUp.current.add(tor.disk_id)
      toast(t("torrents.backupStarted"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doRestoreBackup = async () => {
    const tor = menuFor
    setMenuFor(null)
    if (!tor) return
    try {
      await api.restoreBackup(tor.disk_id)
      restoring.current.add(tor.disk_id)
      toast(t("torrents.backupRestoreStarted"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doDeleteBackup = async (tor: Torrent) => {
    setConfirmDelBackup(null)
    try {
      await api.deleteBackup(tor.disk_id)
      toast(t("torrents.backupDeleted"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  const doTogglePause = async () => {
    const next = !paused
    setPaused(next)
    try {
      await api.setUpscalePaused(next)
      toast(next ? t("torrents.upscalePaused") : t("torrents.upscaleResumed"))
    } catch (e) {
      setPaused(!next)
      toast((e as Error).message, "err")
    }
  }

  const doCancelQueue = async (list: Torrent[]) => {
    try {
      await Promise.all(list.map((tor) => api.cancelUpscale(tor.disk_id)))
      toast(t("torrents.upscaleCancelled"))
      load()
    } catch (e) { toast((e as Error).message, "err") }
  }

  if (torrents === null) {
    return (
      <div className={s.loaderCenter}>
        <Loader size="md"/>
      </div>
    )
  }

  const upscalingTorrents = torrents.filter((tor) => tor.upscaling)
  const queueDone = upscalingTorrents.reduce((n, tor) => n + tor.upscale_done, 0)
  const queueTotal = upscalingTorrents.reduce((n, tor) => n + tor.upscale_total, 0)

  // Active: downloading (progress<1) or any qb torrent with no known category
  const activeTorrents = torrents.filter(
    (tor) => (tor.in_qbittorrent && tor.progress < 1) || tor.category_id == null
  )
  const activeDiskIds = new Set(activeTorrents.map((t) => t.disk_id))
  const restTorrents = torrents.filter((tor) => !activeDiskIds.has(tor.disk_id))

  const catGroups: Map<number, {cat: Category; items: Torrent[]}> = new Map()
  for (const cat of cats) catGroups.set(cat.id, {cat, items: []})
  for (const tor of restTorrents) catGroups.get(tor.category_id!)!.items.push(tor)
  const nonEmptyCats = [...catGroups.values()].filter((g) => g.items.length > 0)

  const isEmpty = activeTorrents.length === 0 && nonEmptyCats.length === 0

  const getPage = (key: string) => catPages[key] ?? 0
  const setPage = (key: string, page: number) =>
    setCatPages((prev) => ({...prev, [key]: page}))

  const renderTorrentItem = (tor: Torrent) => (
    <TorrentItem key={tor.disk_id} tor={tor} onMenu={setMenuFor}/>
  )

  const renderPagination = (key: string, total: number) => {
    const totalPages = Math.ceil(total / PAGE_SIZE)
    if (totalPages <= 1) return null
    const page = Math.min(getPage(key), totalPages - 1)
    return (
      <div className={s.pagination}>
        <button className={s.pageBtn} disabled={page === 0} onClick={() => setPage(key, page - 1)}>
          <ChevronLeft size={16}/>
        </button>
        <span className={s.pageLabel}>{page + 1} / {totalPages}</span>
        <button className={s.pageBtn} disabled={page === totalPages - 1} onClick={() => setPage(key, page + 1)}>
          <ChevronRight size={16}/>
        </button>
      </div>
    )
  }

  const renderCatSection = (key: string, header: string, items: Torrent[]) => {
    const totalPages = Math.ceil(items.length / PAGE_SIZE)
    const page = Math.min(getPage(key), Math.max(0, totalPages - 1))
    const visible = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
    return (
      <div key={key}>
        <ListSection header={header}>{visible.map(renderTorrentItem)}</ListSection>
        {renderPagination(key, items.length)}
      </div>
    )
  }

  return (
    <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      <div className={s.header}>
        <h3 className={s.headerTitle}>{t("torrents.title")}</h3>
        <Button variant="subtle" px={8} onClick={load}><RefreshCw size={20}/></Button>
      </div>

      {pull > 0 && <div className={s.pullHint} style={{height: pull}}>{t("torrents.pull")}</div>}

      <div className={s.content}>
        {isEmpty ? (
          <ListPlaceholder header={t("torrents.empty")} description={t("torrents.emptyHint")}/>
        ) : (
          <>
            {activeTorrents.length > 0 && renderCatSection("active", t("torrents.active"), activeTorrents)}
            {nonEmptyCats.map(({cat, items}) => renderCatSection(String(cat.id), cat.name, items))}
          </>
        )}
      </div>

      {upscalingTorrents.length > 0 && <div style={{height: 72}}/>}

      {upscalingTorrents.length > 0 && (
        <div className={s.queueBar}>
          <div className={s.queueInfo}>
            <Wand2 size={16}/>
            <span>{t("torrents.upscaleQueueLabel", {done: queueDone, total: queueTotal})}</span>
          </div>
          <div className={s.queueActions}>
            <button className={s.iconBtn} onClick={doTogglePause}
                    title={paused ? t("torrents.upscaleResume") : t("torrents.upscalePause")}>
              {paused ? <Play size={20}/> : <Pause size={20}/>}
            </button>
            <button className={`${s.iconBtn} ${s.danger}`} onClick={() => doCancelQueue(upscalingTorrents)}
                    title={t("torrents.upscaleRemoveQueue")}>
              <XCircle size={20}/>
            </button>
          </div>
        </div>
      )}

      <ActionDrawer
        tor={menuFor}
        cats={cats}
        upscalers={upscalers}
        onClose={() => setMenuFor(null)}
        onMove={() => { setMoving(menuFor); setMenuFor(null) }}
        onStructure={doStructure}
        onResolveNames={() => { setRenameFor(menuFor); setMenuFor(null) }}
        onUpscale={() => { setUpscaleFor(menuFor); setMenuFor(null) }}
        onResults={() => { setResultsFor(menuFor); setMenuFor(null) }}
        onDelLinks={() => { setConfirmDelLinks(menuFor); setMenuFor(null) }}
        onDelBackup={() => { setConfirmDelBackup(menuFor); setMenuFor(null) }}
        onDelete={() => { setConfirmDel(menuFor); setMenuFor(null) }}
        onBackup={doBackup}
        onRestoreBackup={doRestoreBackup}
      />

      <UpscaleDrawer
        tor={upscaleFor}
        upscalers={upscalers}
        compressionLevels={compressionLevels}
        upscaleTargets={upscaleTargets}
        defaultTarget={upscaleTarget}
        onClose={() => setUpscaleFor(null)}
        onDone={load}
      />

      <UpscaleResultsDrawer
        tor={resultsFor}
        onClose={() => setResultsFor(null)}
      />

      <RenameJobsDrawer
        tor={renameFor}
        onClose={() => setRenameFor(null)}
        onResolved={load}
      />

      <CategoryPicker
        categories={cats}
        open={!!moving}
        title={t("torrents.move")}
        onPick={(c) => moving && doMove(moving, c)}
        onClose={() => setMoving(null)}
      />

      <ConfirmDrawers
        confirmDel={confirmDel}
        confirmRemove={confirmRemove}
        confirmDelLinks={confirmDelLinks}
        confirmDelBackup={confirmDelBackup}
        onCancelDel={() => setConfirmDel(null)}
        onCancelRemove={() => setConfirmRemove(null)}
        onCancelDelLinks={() => setConfirmDelLinks(null)}
        onCancelDelBackup={() => setConfirmDelBackup(null)}
        onDelete={doDelete}
        onRemoveFromClient={doRemoveFromClient}
        onSwitchToRemove={(tor) => { setConfirmDel(null); setConfirmRemove(tor) }}
        onDeleteLinks={doDeleteLinks}
        onDeleteBackup={doDeleteBackup}
      />
    </div>
  )
}
