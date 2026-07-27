import {useEffect, useState} from "react"
import {Button, Drawer, Loader, TextInput} from "@mantine/core"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import type {RenameJob, Torrent} from "@/types"
import s from "./RenameJobsDrawer.module.scss"

interface Props {
  tor: Torrent | null
  onClose: () => void
  onResolved: () => void
}

export function RenameJobsDrawer({tor, onClose, onResolved}: Props) {
  const {t} = useTranslation()
  const [jobs, setJobs] = useState<RenameJob[] | null>(null)
  const [namingId, setNamingId] = useState<number | null>(null)
  const [value, setValue] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!tor) {
      setJobs(null)
      setNamingId(null)
      setValue("")
      return
    }
    api.renameJobs(tor.disk_id).then((r) => setJobs(r.jobs)).catch((e) => {
      toast((e as Error).message, "err")
      onClose()
    })
  }, [tor]) // eslint-disable-line

  // Drop a resolved job; close + reload once the last one is handled.
  const remove = (id: number) => {
    const next = (jobs ?? []).filter((j) => j.id !== id)
    setJobs(next)
    if (next.length === 0) {
      toast(t("torrents.renameAllDone"), "ok")
      onResolved()
      onClose()
    }
  }

  const doManual = async (job: RenameJob) => {
    const text = value.trim()
    if (!text) return
    setBusy(true)
    try {
      await api.renameJobManual(job.id, text)
      setNamingId(null)
      setValue("")
      remove(job.id)
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setBusy(false)
    }
  }

  const doFlat = async (id: number) => {
    setBusy(true)
    try {
      await api.renameJobFlat(id)
      remove(id)
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setBusy(false)
    }
  }

  const doSkip = async (id: number) => {
    setBusy(true)
    try {
      await api.renameJobSkip(id)
      remove(id)
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setBusy(false)
    }
  }

  const doAll = async (fn: (id: number) => Promise<unknown>) => {
    if (!jobs) return
    setBusy(true)
    try {
      await Promise.all(jobs.map((j) => fn(j.id)))
      toast(t("torrents.renameAllDone"), "ok")
      onResolved()
      onClose()
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setBusy(false)
    }
  }

  const startNaming = (job: RenameJob) => {
    setNamingId(job.id)
    setValue("")
  }

  return (
    <Drawer
      opened={!!tor}
      onClose={onClose}
      title={t("torrents.resolveNames")}
      position="bottom"
      radius="lg"
      overlayProps={{blur: 2}}
      styles={{title: {width: "100%", textAlign: "center"}}}
    >
      {!jobs ? (
        <div className={s.loader}><Loader size="sm"/></div>
      ) : jobs.length === 0 ? (
        <div className={s.empty}>{t("torrents.renameEmpty")}</div>
      ) : (
        <div className={s.body}>
          {jobs.length > 1 && (
            <div className={s.bulk}>
              <Button size="xs" variant="default" disabled={busy}
                      onClick={() => doAll(api.renameJobFlat)}>
                {t("torrents.renameFlatAll")}
              </Button>
              <Button size="xs" variant="default" disabled={busy}
                      onClick={() => doAll(api.renameJobSkip)}>
                {t("torrents.renameSkipAll")}
              </Button>
            </div>
          )}
          {jobs.map((job) => (
            <div key={job.id} className={s.item}>
              <p className={s.name}>{job.filename}</p>
              {namingId === job.id ? (
                <div className={s.naming}>
                  <TextInput
                    placeholder={job.jf_type === "tvshows" ? "S01E04" : "Title (2024)"}
                    description={job.jf_type === "tvshows"
                      ? t("torrents.renameHintTv") : t("torrents.renameHintMovie")}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && doManual(job)}
                    autoFocus
                  />
                  <div className={s.row}>
                    <Button size="xs" disabled={busy || !value.trim()} onClick={() => doManual(job)}>
                      {t("common.save")}
                    </Button>
                    <Button size="xs" variant="default" disabled={busy}
                            onClick={() => setNamingId(null)}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className={s.row}>
                  <Button size="xs" variant="light" disabled={busy} onClick={() => startNaming(job)}>
                    {t("torrents.renameManual")}
                  </Button>
                  <Button size="xs" variant="default" disabled={busy} onClick={() => doFlat(job.id)}>
                    {t("torrents.renameFlat")}
                  </Button>
                  <Button size="xs" variant="subtle" color="red" disabled={busy}
                          onClick={() => doSkip(job.id)}>
                    {t("torrents.renameSkip")}
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Drawer>
  )
}
