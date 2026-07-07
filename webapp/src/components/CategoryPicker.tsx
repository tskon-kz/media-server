import { Drawer } from "@mantine/core";
import { ListItem, ListSection } from "./ui";
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
    <Drawer
      opened={open}
      onClose={onClose}
      title={title ?? "Category"}
      position="bottom"
      radius="lg"
      overlayProps={{ blur: 2 }}
    >
      <ListSection style={{ marginBottom: 16 }}>
        {categories.map((c) => (
          <ListItem key={c.id} onClick={() => onPick(c)}>
            {c.name}
          </ListItem>
        ))}
      </ListSection>
    </Drawer>
  );
}
