import type { ReactNode } from "react";
import { Tabs as RadixTabs } from "radix-ui";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  return (
    <RadixTabs.Root
      value={value}
      onValueChange={onValueChange}
      defaultValue={defaultValue ?? items[0]?.value}
      className={cn("flex min-h-0 flex-col", className)}
    >
      <RadixTabs.List
        // The strip scrolls on its own. Without `overflow-x-auto` a tab that does not fit is
        // still scrolled into view by the browser — by moving the panel beside it, which
        // silently clips the panel's content.
        className={cn(
          "flex gap-1 overflow-x-auto border-b border-border px-1 scroll-thin",
          listClassName,
        )}
        aria-label={t("common.sections")}
      >
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className="relative -mb-px flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-small font-medium text-ink-2 transition-colors hover:text-ink data-[state=active]:border-primary data-[state=active]:text-ink"
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
