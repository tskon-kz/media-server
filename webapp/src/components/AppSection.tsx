import type { ReactNode } from "react";
import styles from './AppSection.module.scss'

interface Props {
  children: ReactNode | ReactNode[];
  title?: string;
}

const AppSection = ({ children, title }: Props) => {
  return (
    <div className={styles.wrapper}>
      {title && (
        <div className={styles.title}>
          {title}
        </div>
      )}
      <div
        className={styles.content}
      >
        {children}
      </div>
    </div>
  );
};

export default AppSection;
