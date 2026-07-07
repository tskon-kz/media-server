import {useCallback, useEffect, useRef, useState} from "react"
import {Box, Button, Drawer, Loader, Progress, Stack, Title} from "@mantine/core"
import {Clapperboard, Folder, FolderInput, Layers, RefreshCw, Trash2} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes, pct, speed} from "@/format"
import {haptic} from "@/telegram"
import {toast} from "@/components/Toast"
import {CategoryPicker} from "@/components/CategoryPicker"
import {TorrentIcon} from "@/icons"
import {ListItem, ListPlaceholder, ListSection} from "@/components/ui"
import type {Category, Torrent} from "@/types"
import s from "./TorrentList.module.scss"

export function TorrentList() {
  const {t} = useTranslation()
  const [torrents, setTorrents] = useState<Torrent[] | null>(null)
  const [cats, setCats] = useState<Category[]>([])
  const [moving, setMoving] = useState<Torrent | null>(null)
  const [structFor, setStructFor] = useState<Torrent | null>(null)
  const [confirmDel, setConfirmDel] = useState<Torrent | null>(null)
  const [pull, setPull] = useState(0)

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
      await api.deleteTorrent(tor.hash);
      toast(t("torrents.deleted"));
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doMove = async (tor: Torrent, cat: Category) => {
    setMoving(null)
    try {
      await api.moveTorrent(tor.hash, cat.id);
      toast(t("torrents.moved", {name: cat.name}));
      load()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const doStructure = async (tor: Torrent, mode: "pretty" | "flat" | "delete") => {
    setStructFor(null)
    try {
      const r = await api.structure(tor.hash, mode)
      if (r.xdev) toast(t("torrents.xdev"), "err")
      else if (mode === "pretty") toast(t("torrents.linked", {n: r.linked, pending: r.pending}))
      else toast(t("common.done"))
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
                key={tor.hash}
                before={<TorrentIcon state={tor.state}/>}
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
                subtitle={`${tor.progress < 1 ? pct(tor.progress) + " · " : ""}${bytes(tor.size)}${tor.dlspeed > 0 ? " · ↓ " + speed(tor.dlspeed) : ""}`}
                description={
                  tor.progress < 1
                    ? <Progress value={tor.progress * 100} size="xs" mt={6}/>
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
            {t("common.delete")}
          </Button>
          <Button fullWidth variant="default" onClick={() => setConfirmDel(null)}>
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
        </Stack>
      </Drawer>
    </Box>
  )
}
