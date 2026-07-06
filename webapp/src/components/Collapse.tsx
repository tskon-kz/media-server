import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import s from "./Collapse.module.scss";

interface Props {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function Collapse({ title, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <button className={s.header} onClick={() => setOpen((o) => !o)}>
        <span>{title}</span>
        <ChevronDown size={15} className={`${s.chevron} ${open ? s.chevronOpen : ""}`} />
      </button>
      <div className={`${s.body} ${open ? s.bodyOpen : ""}`}>
        <div className={s.inner}>{children}</div>
      </div>
    </div>
  );
}
