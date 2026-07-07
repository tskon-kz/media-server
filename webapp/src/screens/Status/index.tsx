import {useEffect, useState} from "react"
import {Divider, Loader} from "@mantine/core"
import {CheckCircle2, XCircle} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {speed} from "@/format"
import PageHeader from "@/components/PageHeader"
import Section from "@/components/Section"
import styles from "./Status.module.scss"

export function Status() {
  const {t} = useTranslation()
  const [st, setSt] = useState<{ connected: boolean; dl?: number; ul?: number } | null>(null)

  useEffect(() => {
    const load = () => api.status().then(setSt).catch(() => setSt({connected: false}))
    load()
    const iv = setInterval(load, 2000)
    return () => clearInterval(iv)
  }, [])

  const statusIcon = st
    ? st.connected
      ? <CheckCircle2 size={16} color="var(--tg-theme-link-color)"/>
      : <XCircle size={16} color="var(--tg-theme-destructive-text-color)"/>
    : <Loader size={16}/>

  return (
    <div>
      <PageHeader title={t("status.title")}/>

      <div className={styles.content}>
        <Section title={t("status.services")}>
          <div className={styles.row}>
            <span>qBittorrent</span>
            {statusIcon}
          </div>
        </Section>

        <Section title={t("status.transfer")}>
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
      </div>
    </div>
  )
}
