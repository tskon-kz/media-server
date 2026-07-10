import {useCallback, useEffect, useRef, useState} from "react"
import {Box, Button, Checkbox, Divider, Drawer, Loader, Progress, SegmentedControl, Stack, Title} from "@mantine/core"
import {Collapse} from "@/components/Collapse"
import {Clapperboard, Folder, FolderInput, HardDrive, ListChecks, MoreHorizontal, Pause, Play, RefreshCw, Save, Trash2, Wand2, XCircle} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes, pct, speed} from "@/format"
import {haptic} from "@/telegram"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {TorrentIcon} from "@/icons"
import {ListItem, ListPlaceholder, ListSection} from "@/components/ui"
import type {Category, CompressionLevel, Torrent, Upscaler, UpscaleInfo, UpscaleResult, UpscaleTarget} from "@/types"
import s from "./TorrentList.module.scss"

export function TorrentList() {
  const {t} = useTranslation()
  const [torrents, setTorrents] = useState<Torrent[] | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [moving, setMoving] = useState<Torrent | null>(null)
  const [menuFor, setMenuFor] = useState<Torrent | null>(null)
  const [upscaleFor, setUpscaleFor] = useState<Torrent | null>(null)
  const [upscalers, setUpscalers] = useState<Upscaler[]>([])
  const [compressionLevels, setCompressionLevels] = useState<CompressionLevel[]>([])
  const [compression, setCompression] = useState("balanced")
  const [upscaleTargets, setUpscaleTargets] = useState<UpscaleTarget[]>([])
  const [upscaleTarget, setUpscaleTarget] = useState("2x")
  const [paused, setPaused] = useState(false)
  const [upInfo, setUpInfo] = useState<UpscaleInfo | null>(null)
  const [upNames, setUpNames] = useState<string[]>([])
  const [resultsFor, setResultsFor] = useState<Torrent | null>(null)
  const [results, setResults] = useState<UpscaleResult[] | null>(null)
  const [confirmDel, setConfirmDel] = useState<Torrent | null>(null)
  const [confirmDelLinks, setConfirmDelLinks] = useState<Torrent | null>(null)
  const [confirmDelBackup, setConfirmDelBackup] = useState<Torrent | null>(null)
  const [pull, setPull] = useState(0)
  const [confirmRemove, setConfirmRemove] = useState<Torrent | null>(null)

  // disk_ids with a backup copy in flight, so we can toast when it completes.
  const backingUp = useRef<Set<string>>(new Set())
  // disk_ids with a restore copy in flight, so we can toast when it completes.
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
      setPaused(!!c.upscale_paused)
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
    setMenuFor(null)
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

  const openUpscale = async (tor: Torrent) => {
    setUpscaleFor(tor)
    setMenuFor(null)
    setUpInfo(null)
    try {
      const info = await api.upscaleInfo(tor.disk_id)
      setUpInfo(info)
      // Already-upscaled files aren't returned, so pre-check everything.
      setUpNames(info.groups.flatMap((g) => g.files.map((f) => f.name)))
    } catch (e) {
      setUpscaleFor(null)
      toast((e as Error).message, "err")
    }
  }

  const doUpscale = async (tor: Torrent, upscalerId: string) => {
    // Multi-file: send the checked file names. Single file: nothing — the whole
    // thing is queued.
    const multiFile = !!upInfo && upInfo.total > 1
    if (multiFile && upNames.length === 0) {
      toast(t("torrents.upscaleNoFiles"), "err")
      return
    }
    const sel = multiFile ? {names: upNames} : {}
    setUpscaleFor(null)
    setMenuFor(null)
    try {
      const r = await api.upscale(tor.disk_id, upscalerId, compression, upscaleTarget, sel)
      toast(t("torrents.upscaleQueued", {n: r.queued}))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const toggleUpName = (name: string) =>
    setUpNames((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name])

  // Select/deselect every file in a group (season). Toggles to whichever state
  // isn't already fully applied.
  const toggleGroup = (names: string[]) =>
    setUpNames((prev) => {
      const allOn = names.every((n) => prev.includes(n))
      const rest = prev.filter((n) => !names.includes(n))
      return allOn ? rest : [...rest, ...names]
    })

  // Scrollable checkbox list + a scoped select/deselect-all for one group.
  const renderUpGroup = (names: string[], files: {name: string; label: string}[]) => {
    const allOn = names.length > 0 && names.every((n) => upNames.includes(n))
    return (
      <>
        <Box style={{display: "flex", justifyContent: "flex-end"}}>
          <Button variant="subtle" size="compact-xs" onClick={() => toggleGroup(names)}>
            {allOn ? t("torrents.deselectAll") : t("torrents.selectAll")}
          </Button>
        </Box>
        <Box style={{
          maxHeight: 260, overflowY: "auto",
          background: "rgba(128, 128, 128, 0.08)",
          borderRadius: 10, padding: "8px 10px",
        }}>
          <Stack gap={6}>
            {files.map((f) => (
              <Checkbox
                key={f.name}
                label={f.label}
                checked={upNames.includes(f.name)}
                onChange={() => toggleUpName(f.name)}
                styles={{label: {fontSize: 13, wordBreak: "break-all"}}}
              />
            ))}
          </Stack>
        </Box>
      </>
    )
  }

  const doTogglePause = async () => {
    const next = !paused
    setPaused(next)
    setMenuFor(null)
    try {
      await api.setUpscalePaused(next)
      toast(next ? t("torrents.upscalePaused") : t("torrents.upscaleResumed"))
    } catch (e) {
      setPaused(!next)
      toast((e as Error).message, "err")
    }
  }

  const doCancelQueue = async (tor: Torrent) => {
    setMenuFor(null)
    try {
      await api.cancelUpscale(tor.disk_id)
      toast(t("torrents.upscaleCancelled"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const openResults = async (tor: Torrent) => {
    setResultsFor(tor)
    setMenuFor(null)
    setResults(null)
    try {
      const r = await api.upscaleResults(tor.disk_id)
      setResults(r.results)
    } catch (e) {
      setResultsFor(null)
      toast((e as Error).message, "err")
    }
  }

  const doBackup = async (tor: Torrent) => {
    setMenuFor(null)
    try {
      await api.backup(tor.disk_id)
      backingUp.current.add(tor.disk_id)
      toast(t("torrents.backupStarted"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doRestoreBackup = async (tor: Torrent) => {
    setMenuFor(null)
    try {
      await api.restoreBackup(tor.disk_id)
      restoring.current.add(tor.disk_id)
      toast(t("torrents.backupRestoreStarted"))
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doDeleteBackup = async (tor: Torrent) => {
    setConfirmDelBackup(null)
    setMenuFor(null)
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
                    <button
                      className={s.iconBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuFor(tor)
                      }}
                      title={t("torrents.actions")}
                    >
                      <MoreHorizontal size={18}/>
                    </button>
                  </div>
                }
                subtitle={`${tor.progress < 1 ? pct(tor.progress) + " · " : ""}${tor.size != null ? bytes(tor.size) : t("torrents.sizeUnknown")}${tor.dlspeed > 0 ? " · ↓ " + speed(tor.dlspeed) : ""}${tor.upscaling ? " · ✨ " + t("torrents.upscaling", {done: tor.upscale_done, total: tor.upscale_total, pct: pct(tor.upscale_progress)}) : ""}${tor.backing_up ? " · 💾 " + t("torrents.backingUp") : ""}${tor.restoring ? " · ♻️ " + t("torrents.restoring") : ""}`}
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
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.deleteBody", {name: confirmDel?.name})}
          </Box>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDel && doDelete(confirmDel)}>
            {confirmDel?.in_qbittorrent ? t("common.delete") : t("torrents.deleteFromDisk")}
          </Button>
          {confirmDel?.in_qbittorrent && (
            <Button fullWidth variant="light" leftSection={<HardDrive size={18}/>}
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
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.removeFromClientBody")}
          </Box>
          <Button fullWidth variant="light" leftSection={<HardDrive size={18}/>}
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
        opened={!!menuFor}
        onClose={() => setMenuFor(null)}
        title={menuFor?.name ?? t("torrents.actions")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <Stack gap={8} pb={16} px={4}>
          {cats.length > 0 && (
            <Button fullWidth variant="default" leftSection={<FolderInput size={18}/>}
                    onClick={() => { setMoving(menuFor); setMenuFor(null) }}>
              {t("torrents.move")}
            </Button>
          )}
          {menuFor?.renameable && (
            <>
              <Button fullWidth variant="default" leftSection={<Clapperboard size={18}/>}
                      onClick={() => menuFor && doStructure(menuFor, "pretty")}>
                {t("torrents.pretty")}
              </Button>
              <Button fullWidth variant="default" leftSection={<Folder size={18}/>}
                      onClick={() => menuFor && doStructure(menuFor, "flat")}>
                {t("torrents.original")}
              </Button>
              <Button fullWidth variant="outline" color="red" leftSection={<Trash2 size={18}/>}
                      onClick={() => { setConfirmDelLinks(menuFor); setMenuFor(null) }}>
                {t("torrents.delLinks")}
              </Button>
              <Divider my={4}/>
              <Button fullWidth variant="default" leftSection={<Wand2 size={18}/>}
                      disabled={upscalers.length === 0 || !!menuFor?.upscaling}
                      onClick={() => menuFor && openUpscale(menuFor)}>
                {t("torrents.upscale")}
              </Button>
              {menuFor?.has_upscale_results && (
                <Button fullWidth variant="default" leftSection={<ListChecks size={18}/>}
                        onClick={() => menuFor && openResults(menuFor)}>
                  {t("torrents.upscaleResults")}
                </Button>
              )}
              {menuFor?.upscaling && (
                <>
                  <Button fullWidth variant="default"
                          leftSection={paused ? <Play size={18}/> : <Pause size={18}/>}
                          onClick={doTogglePause}>
                    {paused ? t("torrents.upscaleResume") : t("torrents.upscalePause")}
                  </Button>
                  <Button fullWidth variant="outline" color="red" leftSection={<XCircle size={18}/>}
                          onClick={() => menuFor && doCancelQueue(menuFor)}>
                    {t("torrents.upscaleRemoveQueue")}
                  </Button>
                </>
              )}
            </>
          )}
          {menuFor?.backing_up ? (
            <Button fullWidth variant="default" leftSection={<Loader size={16}/>} disabled>
              {t("torrents.backingUp")}
            </Button>
          ) : menuFor?.restoring ? (
            <Button fullWidth variant="default" leftSection={<Loader size={16}/>} disabled>
              {t("torrents.restoring")}
            </Button>
          ) : menuFor?.has_backup ? (
            <Button fullWidth variant="default" leftSection={<Save size={18}/>}
                    onClick={() => menuFor && doRestoreBackup(menuFor)}>
              {t("torrents.restoreBackup")}
            </Button>
          ) : (
            <Button fullWidth variant="default" leftSection={<Save size={18}/>}
                    onClick={() => menuFor && doBackup(menuFor)}>
              {t("torrents.backup")}
            </Button>
          )}
          {menuFor?.has_backup && !menuFor?.restoring && (
            <Button fullWidth variant="outline" color="red" leftSection={<Trash2 size={18}/>}
                    onClick={() => { setConfirmDelBackup(menuFor); setMenuFor(null) }}>
              {t("torrents.delBackup")}
            </Button>
          )}
          <Divider my={4}/>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => { setConfirmDel(menuFor); setMenuFor(null) }}>
            {t("common.delete")}
          </Button>
        </Stack>
      </Drawer>

      <Drawer
        opened={!!confirmDelLinks}
        onClose={() => setConfirmDelLinks(null)}
        title={t("torrents.delLinksTitle")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.delLinksBody")}
          </Box>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDelLinks && doStructure(confirmDelLinks, "delete")}>
            {t("torrents.delLinks")}
          </Button>
          <Button fullWidth variant="default" onClick={() => setConfirmDelLinks(null)}>
            {t("common.cancel")}
          </Button>
        </Stack>
      </Drawer>

      <Drawer
        opened={!!confirmDelBackup}
        onClose={() => setConfirmDelBackup(null)}
        title={t("torrents.delBackupTitle")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        <Stack gap={8} pb={16} px={4}>
          <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 4}}>
            {t("torrents.delBackupBody")}
          </Box>
          <Button fullWidth variant="light" color="red" leftSection={<Trash2 size={18}/>}
                  onClick={() => confirmDelBackup && doDeleteBackup(confirmDelBackup)}>
            {t("torrents.delBackup")}
          </Button>
          <Button fullWidth variant="default" onClick={() => setConfirmDelBackup(null)}>
            {t("common.cancel")}
          </Button>
        </Stack>
      </Drawer>

      <Drawer
        opened={!!upscaleFor}
        onClose={() => setUpscaleFor(null)}
        title={t("torrents.upscalePick")}
        position="bottom"
        radius="lg"
        size="85%"
        overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        {!upInfo ? (
          <Box style={{textAlign: "center", padding: "24px 0"}}>
            <Loader size="sm"/>
          </Box>
        ) : (
        <Stack gap={8} pb={16} px={4}>
          {upInfo.total > 1 && (
            <>
              {upInfo.parsed
                ? upInfo.groups.map((g) => {
                    const names = g.files.map((f) => f.name)
                    const sel = names.filter((n) => upNames.includes(n)).length
                    const title = g.season != null ? t("torrents.season", {n: g.season}) : t("torrents.upscaleOther")
                    return (
                      <Collapse key={g.season ?? "other"} variant="plain"
                                title={`${title} · ${sel}/${names.length}`}>
                        {renderUpGroup(names, g.files)}
                      </Collapse>
                    )
                  })
                : renderUpGroup(
                    upInfo.groups.flatMap((g) => g.files.map((f) => f.name)),
                    upInfo.groups.flatMap((g) => g.files),
                  )}
              <Divider my={4}/>
            </>
          )}
          {upscaleTargets.length > 0 && (
            <>
              <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 13}}>
                {t("settings.upscaleTarget")}
              </Box>
              <SegmentedControl
                fullWidth
                value={upscaleTarget}
                onChange={setUpscaleTarget}
                data={upscaleTargets.map((u) => ({value: u.id, label: u.label}))}
              />
              <Divider my={4}/>
            </>
          )}
          {compressionLevels.length > 0 && (
            <>
              <Box style={{color: "var(--tg-theme-hint-color)", fontSize: 13}}>
                {t("torrents.compression")}
              </Box>
              <SegmentedControl
                fullWidth
                value={compression}
                onChange={setCompression}
                data={compressionLevels.map((c) => ({
                  value: c.id,
                  label: t(`torrents.compression_${c.id}`, {defaultValue: c.label}),
                }))}
              />
              <Divider my={4}/>
            </>
          )}
          {upscalers.map((u) => (
            <Button key={u.id} fullWidth variant="light" leftSection={<Wand2 size={18}/>}
                    onClick={() => upscaleFor && doUpscale(upscaleFor, u.id)}>
              {u.label}{u.needs_gpu ? ` · ${t("torrents.gpuHint")}` : ""}
            </Button>
          ))}
        </Stack>
        )}
      </Drawer>

      <Drawer
        opened={!!resultsFor}
        onClose={() => setResultsFor(null)}
        title={t("torrents.upscaleResults")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
        styles={{title: {width: "100%", textAlign: "center"}}}
      >
        {!results ? (
          <Box style={{textAlign: "center", padding: "24px 0"}}>
            <Loader size="sm"/>
          </Box>
        ) : results.length === 0 ? (
          <Box style={{textAlign: "center", padding: "24px 0", color: "var(--tg-theme-hint-color)", fontSize: 14}}>
            {t("torrents.upscaleResultsEmpty")}
          </Box>
        ) : (
          <Stack gap={10} pb={16} px={4}>
            {results.map((r) => (
              <Box key={r.name} style={{borderBottom: "1px solid var(--tg-theme-secondary-bg-color)", paddingBottom: 8}}>
                <Box style={{fontSize: 14, color: "var(--tg-theme-text-color)", wordBreak: "break-all"}}>
                  {r.name}
                </Box>
                <Box style={{fontSize: 13, color: "var(--tg-theme-hint-color)", marginTop: 2}}>
                  {`${r.upscaler} · ${r.target} · ${t(`torrents.compression_${r.compression}`, {defaultValue: r.compression})}`}
                </Box>
              </Box>
            ))}
          </Stack>
        )}
      </Drawer>
    </Box>
  )
}
