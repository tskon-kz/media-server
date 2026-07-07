import {useEffect, useState} from "react"
import {Divider, Loader} from "@mantine/core"
import {CheckCircle2, XCircle} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {bytes, speed} from "@/format"
import PageHeader from "@/components/PageHeader"
import Section from "@/components/Section"
import styles from "./Status.module.scss"

type StatusData = Awaited<ReturnType<typeof api.status>>

function ServiceIcon({ok}: { ok: boolean | undefined }) {
  if (ok === undefined) return <Loader size={16}/>
  return ok
    ? <CheckCircle2 size={16} color="var(--tg-theme-link-color)"/>
    : <XCircle size={16} color="var(--tg-theme-destructive-text-color)"/>
}

export function Status() {
  const {t} = useTranslation()
  const [st, setSt] = useState<StatusData | null>(null)

  useEffect(() => {
    const load = () => api.status().then(setSt).catch(() => setSt({connected: false}))
    load()
    const iv = setInterval(load, 5000)
    return () => clearInterval(iv)
  }, [])

  const connected = st?.connected ?? undefined

  return (
    <div>
      <PageHeader title={t("status.title")}/>

      <div className={styles.content}>
        <Section title={t("status.services")} className="mb-12">
          <div className={styles.row}>
            <span>qBittorrent</span>
            <ServiceIcon ok={connected}/>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>Jellyfin</span>
            <ServiceIcon ok={st ? st.jf_connected : undefined}/>
          </div>
        </Section>

        <Section title={t("status.transfer")} className="mb-12">
          <div className={styles.row}>
            <span>{t("status.download")}</span>
            <span className={styles.rowValue}>{st?.connected ? speed(st.dl ?? 0) : "—"}</span>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>{t("status.upload")}</span>
            <span className={styles.rowValue}>{st?.connected ? speed(st.ul ?? 0) : "—"}</span>
          </div>
        </Section>

        <Section title={t("status.session")} className="mb-12">
          <div className={styles.row}>
            <span>{t("status.sessionDl")}</span>
            <span className={styles.rowValue}>{st?.connected ? bytes(st.dl_data ?? 0) : "—"}</span>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>{t("status.sessionUl")}</span>
            <span className={styles.rowValue}>{st?.connected ? bytes(st.ul_data ?? 0) : "—"}</span>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>{t("status.diskFree")}</span>
            <span className={styles.rowValue}>{st?.connected ? bytes(st.free_space ?? 0) : "—"}</span>
          </div>
        </Section>

        <Section title={t("status.torrentsSection")}>
          <div className={styles.row}>
            <span>{t("status.downloading")}</span>
            <span className={styles.rowValue}>{st?.connected ? (st.torrents_downloading ?? 0) : "—"}</span>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>{t("status.seeding")}</span>
            <span className={styles.rowValue}>{st?.connected ? (st.torrents_seeding ?? 0) : "—"}</span>
          </div>
          <Divider/>
          <div className={styles.row}>
            <span>{t("status.total")}</span>
            <span className={styles.rowValue}>{st?.connected ? (st.torrents_total ?? 0) : "—"}</span>
          </div>
        </Section>
      </div>
    </div>
  )
}
