import { Cell, List, Modal, Section } from "@telegram-apps/telegram-ui";
import type { Category } from "../types";

export function CategoryPicker({
  categories, title, open, onPick, onClose,
}: {
  categories: Category[];
  title?: string;
  open: boolean;
  onPick: (cat: Category) => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={(o) => !o && onClose()}
      header={<Modal.Header>{title ?? "Category"}</Modal.Header>}
    >
      <List>
        <Section>
          {categories.map((c) => (
            <Cell key={c.id} onClick={() => onPick(c)}>
              {c.name}
            </Cell>
          ))}
        </Section>
      </List>
    </Modal>
  );
}
