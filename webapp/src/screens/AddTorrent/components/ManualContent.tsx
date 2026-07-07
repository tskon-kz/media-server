import {type RefObject} from "react"
import {Button, FileInput, Textarea} from "@mantine/core"
import {useTranslation} from "react-i18next"
import styles from "./ManualContent.module.scss"

interface Props {
  magnet: string
  onMagnetChange: (v: string) => void
  busy: boolean
  fileKey: number
  textareaRef: RefObject<HTMLTextAreaElement | null>
  onSubmitMagnet: () => void
  onFile: (f: File | null) => void
}

export function ManualContent(props: Props) {
  const {t} = useTranslation()
  return (
    <div className={styles.root}>
      <div className={styles.section}>
        <Textarea
          label={t("add.magnetSection")}
          ref={props.textareaRef}
          className="mb-12"
          placeholder="magnet:?xt=urn:btih:…"
          value={props.magnet}
          onChange={(e) => props.onMagnetChange(e.target.value)}
          autosize
          minRows={2}
        />

        <Button fullWidth disabled={props.busy || !props.magnet.trim()} onClick={props.onSubmitMagnet}>
          {t("add.addMagnet")}
        </Button>
      </div>

      <div className={styles.section}>
        <FileInput
          key={props.fileKey}
          label={t("add.uploadLabel")}
          accept=".torrent"
          onChange={props.onFile}
          clearable
        />
      </div>
    </div>
  )
}
