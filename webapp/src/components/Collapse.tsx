import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./Collapse.module.scss";

interface Props {
  className?: string
  title: ReactNode;
  children: ReactNode | ReactNode[];
  defaultOpen?: boolean;
  variant?: "plain";
}

export function Collapse(props: Props) {
  const [open, setOpen] = useState(props.defaultOpen ?? false);

  return (
    <div className={`${styles.card}${props.className ? ` ${props.className}` : ""}`}>
      <button
        className={`${styles.header} ${props.variant === "plain" ? styles.headerPlain : ""} ${open ? styles.headerOpen : ""}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{props.title}</span>
        <ChevronDown size={15} className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`} />
      </button>
      <div className={`${styles.body} ${open ? styles.bodyOpen : ""}`}>
        <div className={styles.inner}>
          <div className={styles.content}>{props.children}</div>
        </div>
      </div>
    </div>
  );
}
