import type {ReactNode} from "react";
import styles from './AppSection.module.scss'

interface Props {
  children: ReactNode | ReactNode[]
  title?: string
}

const AppSection = (props: Props) => {
  return (
    <div className={styles.wrapper}>
      {props.title && (<div className={styles.title}>{props.title}</div>)}

      <div className={styles.content}>
        {props.children}
      </div>
    </div>
  )
}

export default AppSection