import styles from './PageHeader.module.scss';

interface Props {
  title: string;
}

const PageHeader = ({ title }: Props) => {
  return (
    <div className={styles.wrapper}>
      <h1 className={styles.title}>{title}</h1>
    </div>
  );
};

export default PageHeader;
