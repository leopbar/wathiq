import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export interface ChipOption<T extends string> {
  value: T;
  label: string;
  count?: number;
}

export function FilterChips<T extends string>({
  options,
  selected,
  onToggle,
  legend,
  className,
}: {
  options: ChipOption<T>[];
  selected: T[];
  onToggle: (value: T) => void;
  legend: string;
  className?: string;
}) {
  return (
    <fieldset className={cn("flex flex-wrap items-center gap-1.5", className)}>
      <legend className="sr-only">{legend}</legend>
      {options.map((option) => {
        const active = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onToggle(option.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-caption font-medium transition-colors",
              active
                ? "border-primary/40 bg-primary-soft text-primary"
                : "border-border bg-surface text-ink-2 hover:bg-surface-2 hover:text-ink",
            )}
          >
            {active ? <Check className="h-3 w-3" aria-hidden /> : null}
            {option.label}
            {option.count !== undefined ? (
              <span className="tabular opacity-70">{option.count}</span>
            ) : null}
          </button>
        );
      })}
    </fieldset>
  );
}
