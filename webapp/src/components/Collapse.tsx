import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./Collapse.module.scss";

interface Props {
  title: string;
  children: ReactNode | ReactNode[];
  defaultOpen?: boolean;
}

export function Collapse(props: Props) {
  const [open, setOpen] = useState(props.defaultOpen ?? false);

  return (
    <div>
      <button className={styles.header} onClick={() => setOpen((o) => !o)}>
        <span>{props.title}</span>
        <ChevronDown size={15} className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`} />
      </button>
      <div className={`${styles.body} ${open ? styles.bodyOpen : ""}`}>
        <div className={styles.inner}>{props.children}</div>
      </div>
    </div>
  );
}
