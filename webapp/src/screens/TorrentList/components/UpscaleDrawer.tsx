import {useEffect, useState} from "react"
import {Button, Checkbox, Divider, Drawer, Loader, SegmentedControl} from "@mantine/core"
import {Wand2} from "lucide-react"
import {useTranslation} from "react-i18next"
import {Collapse} from "@/components/Collapse"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import type {CompressionLevel, Torrent, UpscaleInfo, Upscaler, UpscaleTarget} from "@/types"
import s from "./UpscaleDrawer.module.scss"

interface Props {
  tor: Torrent | null
  upscalers: Upscaler[]
  compressionLevels: CompressionLevel[]
  upscaleTargets: UpscaleTarget[]
  defaultTarget: string
  onClose: () => void
  onDone: () => void
}

export function UpscaleDrawer({
  tor, upscalers, compressionLevels, upscaleTargets, defaultTarget, onClose, onDone,
}: Props) {
  const {t} = useTranslation()
  const [upInfo, setUpInfo] = useState<UpscaleInfo | null>(null)
  const [upNames, setUpNames] = useState<string[]>([])
  const [compression, setCompression] = useState("balanced")
  const [upscaleTarget, setUpscaleTarget] = useState(defaultTarget)

  useEffect(() => {
    if (!tor) {
      setUpInfo(null)
      setUpNames([])
      return
    }
    api.upscaleInfo(tor.disk_id).then((info) => {
      setUpInfo(info)
      setUpNames(info.groups.flatMap((g) => g.files.map((f) => f.name)))
    }).catch((e) => {
      toast((e as Error).message, "err")
      onClose()
    })
  }, [tor]) // eslint-disable-line

  const toggleName = (name: string) =>
    setUpNames((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name])

  const toggleGroup = (names: string[]) =>
    setUpNames((prev) => {
      const allOn = names.every((n) => prev.includes(n))
      const rest = prev.filter((n) => !names.includes(n))
      return allOn ? rest : [...rest, ...names]
    })

  const doUpscale = async (upscalerId: string) => {
    if (!tor) return
    const multiFile = !!upInfo && upInfo.total > 1
    if (multiFile && upNames.length === 0) {
      toast(t("torrents.upscaleNoFiles"), "err")
      return
    }
    const sel = multiFile ? {names: upNames} : {}
    onClose()
    try {
      const r = await api.upscale(tor.disk_id, upscalerId, compression, upscaleTarget, sel)
      toast(t("torrents.upscaleQueued", {n: r.queued}))
      onDone()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  const renderGroup = (names: string[], files: {name: string; label: string}[]) => {
    const allOn = names.length > 0 && names.every((n) => upNames.includes(n))
    return (
      <>
        <div className={s.groupHeader}>
          <Button variant="subtle" size="compact-xs" onClick={() => toggleGroup(names)}>
            {allOn ? t("torrents.deselectAll") : t("torrents.selectAll")}
          </Button>
        </div>
        <div className={s.fileList}>
          <div className={s.fileStack}>
            {files.map((f) => (
              <Checkbox
                key={f.name}
                label={f.label}
                checked={upNames.includes(f.name)}
                onChange={() => toggleName(f.name)}
                styles={{label: {fontSize: 13, wordBreak: "break-all"}}}
              />
            ))}
          </div>
        </div>
      </>
    )
  }

  return (
    <Drawer
      opened={!!tor}
      onClose={onClose}
      title={t("torrents.upscalePick")}
      position="bottom"
      radius="lg"
      size="85%"
      overlayProps={{blur: 2}}
      styles={{title: {width: "100%", textAlign: "center"}}}
    >
      {!upInfo ? (
        <div className={s.loader}>
          <Loader size="sm"/>
        </div>
      ) : (
        <div className={s.body}>
          {upInfo.total > 1 && (
            <>
              {upInfo.parsed
                ? upInfo.groups.map((g) => {
                  const names = g.files.map((f) => f.name)
                  const sel = names.filter((n) => upNames.includes(n)).length
                  const title = g.season != null
                    ? t("torrents.season", {n: g.season})
                    : t("torrents.upscaleOther")
                  return (
                    <Collapse key={g.season ?? "other"} variant="plain"
                              title={`${title} · ${sel}/${names.length}`}>
                      {renderGroup(names, g.files)}
                    </Collapse>
                  )
                })
                : renderGroup(
                  upInfo.groups.flatMap((g) => g.files.map((f) => f.name)),
                  upInfo.groups.flatMap((g) => g.files),
                )}
              <Divider my={4}/>
            </>
          )}
          {upscaleTargets.length > 0 && (
            <>
              <p className={s.label}>{t("settings.upscaleTarget")}</p>
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
              <p className={s.label}>{t("torrents.compression")}</p>
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
                    onClick={() => doUpscale(u.id)}>
              {u.label}{u.needs_gpu ? ` · ${t("torrents.gpuHint")}` : ""}
            </Button>
          ))}
        </div>
      )}
    </Drawer>
  )
}
