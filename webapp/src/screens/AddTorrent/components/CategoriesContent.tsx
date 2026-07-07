import {Button} from "@mantine/core"
import {Plus, Trash2} from "lucide-react"
import {useTranslation} from "react-i18next"
import {ListItem, ListSection} from "@/components/ui"
import type {Category} from "@/types"
import styles from "./CategoriesContent.module.scss"

const DEL_COLOR = "var(--tg-theme-destructive-text-color)"

interface CategoriesContentProps {
  cats: Category[]
  onDelete: (c: Category) => void
  onRename: (c: Category) => void
  onAdd: () => void
}

export function CategoriesContent({cats, onDelete, onRename, onAdd}: CategoriesContentProps) {
  const {t} = useTranslation()
  return (
    <div className={styles.root}>
      <ListSection>
        {cats.map((c) => (
          <ListItem
            key={c.id}
            subtitle={c.path.replace("/media/", "")}
            after={
              <Button
                variant="subtle"
                size="compact-sm"
                px={4}
                style={{color: DEL_COLOR}}
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(c)
                }}
              >
                <Trash2 size={18}/>
              </Button>
            }
            onClick={() => onRename(c)}
            multiline
          >
            {c.name}
          </ListItem>
        ))}
      </ListSection>
      <Button fullWidth variant="dark" leftSection={<Plus size={18}/>} onClick={onAdd}>
        {t("settings.addCategory")}
      </Button>
    </div>
  )
}
