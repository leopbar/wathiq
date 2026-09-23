import { Search, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";

export function SearchInput({
  value,
  onChange,
  placeholder: placeholderProp,
  id,
  className,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  id?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  const placeholder = placeholderProp ?? t("common.searchEllipsis");
  return (
    <div className={cn("relative", className)}>
      <Search
        className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-2"
        aria-hidden
      />
      <input
        id={id}
        type="search"
        value={value}
        aria-label={ariaLabel ?? placeholder}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-[var(--radius)] border border-border bg-surface ps-9 pe-8 text-body text-ink placeholder:text-ink-2/70 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary [&::-webkit-search-cancel-button]:hidden"
      />
      {value ? (
        <button
          type="button"
          aria-label={t("common.clearSearch")}
          onClick={() => onChange("")}
          className="absolute end-2 top-1/2 -translate-y-1/2 rounded-[var(--radius-sm)] p-1 text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
