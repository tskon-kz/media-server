import {useEffect, useState} from "react"
import {Drawer, Loader} from "@mantine/core"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import type {Torrent, UpscaleResult} from "@/types"
import s from "./UpscaleResultsDrawer.module.scss"

interface Props {
  tor: Torrent | null
  onClose: () => void
}

export function UpscaleResultsDrawer({tor, onClose}: Props) {
  const {t} = useTranslation()
  const [results, setResults] = useState<UpscaleResult[] | null>(null)

  useEffect(() => {
    if (!tor) {
      setResults(null)
      return
    }
    api.upscaleResults(tor.disk_id).then((r) => {
      setResults(r.results)
    }).catch((e) => {
      toast((e as Error).message, "err")
      onClose()
    })
  }, [tor]) // eslint-disable-line

  return (
    <Drawer
      opened={!!tor}
      onClose={onClose}
      title={t("torrents.upscaleResults")}
      position="bottom"
      radius="lg"
      overlayProps={{blur: 2}}
      styles={{title: {width: "100%", textAlign: "center"}}}
    >
      {!results ? (
        <div className={s.loader}>
          <Loader size="sm"/>
        </div>
      ) : results.length === 0 ? (
        <div className={s.empty}>
          {t("torrents.upscaleResultsEmpty")}
        </div>
      ) : (
        <div className={s.body}>
          {results.map((r) => (
            <div key={r.name} className={s.item}>
              <p className={s.name}>{r.name}</p>
              <p className={s.meta}>
                {`${r.upscaler} · ${r.target} · ${t(`torrents.compression_${r.compression}`, {defaultValue: r.compression})}`}
              </p>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  )
}
