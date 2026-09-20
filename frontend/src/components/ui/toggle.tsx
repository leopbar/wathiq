import { Checkbox as RadixCheckbox, Switch as RadixSwitch } from "radix-ui";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export function Checkbox({
  checked,
  onCheckedChange,
  id,
  label,
  className,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id: string;
  label: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <RadixCheckbox.Root
        id={id}
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-border bg-surface data-[state=checked]:border-primary data-[state=checked]:bg-primary"
      >
        <RadixCheckbox.Indicator>
          <Check className="h-3 w-3 text-primary-ink" aria-hidden />
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      <label htmlFor={id} className="cursor-pointer text-small text-ink">
        {label}
      </label>
    </div>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  id,
  label,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id: string;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <RadixSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className="relative h-5 w-9 rounded-full border border-border bg-surface-2 transition-colors data-[state=checked]:border-primary data-[state=checked]:bg-primary disabled:opacity-50"
      >
        <RadixSwitch.Thumb className="block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-ink-2 transition-transform data-[state=checked]:translate-x-[1.125rem] data-[state=checked]:bg-primary-ink" />
      </RadixSwitch.Root>
      <label htmlFor={id} className="cursor-pointer text-small text-ink">
        {label}
      </label>
    </div>
  );
}
