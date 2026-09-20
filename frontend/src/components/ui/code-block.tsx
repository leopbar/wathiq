import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "./button";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => setCopied(false));
  };

  return (
    <Button
      variant="ghost"
      size="iconSm"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
      title={copied ? "Copied" : label}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-success" aria-hidden />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden />
      )}
    </Button>
  );
}

export function CodeBlock({
  code,
  title,
  className,
  maxHeight = "28rem",
}: {
  code: string;
  title?: string;
  className?: string;
  maxHeight?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius)] border border-border bg-surface-2",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-surface px-3 py-1.5">
        <span className="label-caption text-ink-2">{title ?? "Source"}</span>
        <CopyButton value={code} />
      </div>
      <pre
        dir="ltr"
        style={{ maxHeight }}
        className="scroll-thin overflow-auto px-3 py-3 text-caption leading-5 text-ink"
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
