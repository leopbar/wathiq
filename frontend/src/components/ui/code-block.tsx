import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";
import { Button } from "./button";

export function CopyButton({ value, label }: { value: string; label?: string }) {
  const { t } = useTranslation();
  const idle = label ?? t("common.copy");
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
      aria-label={copied ? t("common.copied") : idle}
      title={copied ? t("common.copied") : idle}
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
  const { t } = useTranslation();
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius)] border border-border bg-surface-2",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-surface px-3 py-1.5">
        <span className="label-caption text-ink-2">{title ?? t("common.source")}</span>
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
