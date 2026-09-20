import { Progress as RadixProgress } from "radix-ui";
import { cn } from "@/lib/cn";

export function Progress({
  value,
  label,
  className,
  tone = "primary",
}: {
  value: number;
  label: string;
  className?: string;
  tone?: "primary" | "success" | "warning" | "danger";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const bar = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
  }[tone];

  return (
    <RadixProgress.Root
      value={clamped}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-2", className)}
    >
      <RadixProgress.Indicator
        className={cn("h-full rounded-full transition-[width] duration-500", bar)}
        style={{ width: `${clamped}%` }}
      />
    </RadixProgress.Root>
  );
}
