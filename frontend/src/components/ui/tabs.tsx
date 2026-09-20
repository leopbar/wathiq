import type { ReactNode } from "react";
import { Tabs as RadixTabs } from "radix-ui";
import { cn } from "@/lib/cn";

export interface TabItem {
  value: string;
  label: string;
  badge?: ReactNode;
  content: ReactNode;
}

export function Tabs({
  items,
  value,
  onValueChange,
  defaultValue,
  className,
  listClassName,
}: {
  items: TabItem[];
  value?: string;
  onValueChange?: (value: string) => void;
  defaultValue?: string;
  className?: string;
  listClassName?: string;
}) {
  return (
    <RadixTabs.Root
      value={value}
      onValueChange={onValueChange}
      defaultValue={defaultValue ?? items[0]?.value}
      className={cn("flex min-h-0 flex-col", className)}
    >
      <RadixTabs.List
        className={cn("flex gap-1 border-b border-border px-1", listClassName)}
        aria-label="Sections"
      >
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className="relative -mb-px flex items-center gap-2 border-b-2 border-transparent px-3 py-2 text-small font-medium text-ink-2 transition-colors hover:text-ink data-[state=active]:border-primary data-[state=active]:text-ink"
          >
            {item.label}
            {item.badge}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {items.map((item) => (
        <RadixTabs.Content
          key={item.value}
          value={item.value}
          className="min-h-0 flex-1 focus-visible:outline-none"
        >
          {item.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
