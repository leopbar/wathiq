import { cn } from "@/lib/cn";

/** Neutral product mark: a shield with a check. No bank branding anywhere. */
export function BrandMark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={cn("shrink-0", className)}
    >
      <path
        d="M16 2.5 27 6.2v9.1c0 6.9-4.4 12.6-11 14.2-6.6-1.6-11-7.3-11-14.2V6.2L16 2.5Z"
        fill="currentColor"
        fillOpacity="0.14"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="m10.8 16.2 3.6 3.7 6.8-7.4"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BrandWordmark({
  className,
  subtitle,
}: {
  className?: string;
  subtitle?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark className="text-primary" />
      <div className="leading-tight">
        <p className="text-h2 font-semibold tracking-tight text-ink">Wathiq</p>
        {subtitle ? <p className="text-caption text-ink-2">{subtitle}</p> : null}
      </div>
    </div>
  );
}
