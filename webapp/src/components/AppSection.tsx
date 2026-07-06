import type { ReactNode } from "react";
import styles from './AppSection.module.scss'
import classNames from "classnames";

interface Props {
  className?: string
  children: ReactNode | ReactNode[];
  title?: string;
}

const AppSection = (props: Props) => {
  return (
    <div className={classNames(styles.wrapper, props.className)}>
      {props.title && (
        <div className={styles.title}>
          {props.title}
        </div>
      )}
      <div
        className={styles.content}
      >
        {props.children}
      </div>
    </div>
  );
};

export default AppSection;
