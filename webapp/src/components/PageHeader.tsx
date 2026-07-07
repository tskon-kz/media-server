import styles from './PageHeader.module.scss';
import classNames from "classnames";

interface Props {
  className?: string
  title: string;
}

const PageHeader = (props: Props) => {
  return (
    <div className={classNames(styles.wrapper, props.className)}>
      <h1 className={styles.title}>{props.title}</h1>
    </div>
  );
};

export default PageHeader;
