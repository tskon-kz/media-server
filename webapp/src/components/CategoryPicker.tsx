import {Button, Drawer, Stack} from "@mantine/core"
import type {Category} from "../types"

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
      overlayProps={{blur: 2}}
      styles={{title: {width: "100%", textAlign: "center"}}}
    >
      <Stack gap={8} pb={16} px={4}>
        {categories.map((c) => (
          <Button key={c.id} fullWidth variant="light" onClick={() => onPick(c)}>
            {c.name}
          </Button>
        ))}
      </Stack>
    </Drawer>
  )
}
