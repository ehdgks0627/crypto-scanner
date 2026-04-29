import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

type TabItem = {
  value: string;
  label: ReactNode;
};

export function Tabs({ items, value, onChange }: { items: TabItem[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="ui-tabs">
      {items.map((item) => (
        <button
          type="button"
          key={item.value}
          className={cn("ui-tabs__item", item.value === value && "is-active")}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
