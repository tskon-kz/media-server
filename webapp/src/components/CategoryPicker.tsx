import { Sheet } from "./Sheet";
import type { Category } from "../types";

// Reused wherever the bot would show a category keyboard (add magnet, add file,
// add from search, move). Picking a category resolves the flow in one tap.
export function CategoryPicker({
  categories, title, onPick, onClose,
}: {
  categories: Category[];
  title?: string;
  onPick: (cat: Category) => void;
  onClose: () => void;
}) {
  return (
    <Sheet title={title ?? "Category"} onClose={onClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {categories.map((c) => (
          <button key={c.id} className="secondary full" onClick={() => onPick(c)}>
            {c.name}
          </button>
        ))}
      </div>
    </Sheet>
  );
}
