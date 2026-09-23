import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";
import { cssVar, useTheme } from "./useTheme";
import { ErrorState } from "./ErrorState";
import { Skeleton } from "./ui/skeleton";

let sequence = 0;

/** Renders a Mermaid source string and re-renders whenever the theme flips. */
export function MermaidDiagram({
  chart,
  className,
  ariaLabel,
}: {
  chart: string;
  className?: string;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const baseId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setError(null);

    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: cssVar("--font-sans", "Inter, sans-serif"),
      themeVariables: {
        background: cssVar("--color-surface", "#fff"),
        primaryColor: cssVar("--color-primary-soft", "#e6f2f1"),
        primaryTextColor: cssVar("--color-ink", "#0b1220"),
        primaryBorderColor: cssVar("--color-primary", "#0e5e5a"),
        secondaryColor: cssVar("--color-surface-2", "#f1f3f7"),
        tertiaryColor: cssVar("--color-surface", "#fff"),
        lineColor: cssVar("--color-ink-2", "#5a6675"),
        textColor: cssVar("--color-ink", "#0b1220"),
        mainBkg: cssVar("--color-surface-2", "#f1f3f7"),
        nodeBorder: cssVar("--color-border", "#e3e7ee"),
        clusterBkg: cssVar("--color-bg", "#f7f8fa"),
        clusterBorder: cssVar("--color-border", "#e3e7ee"),
        edgeLabelBackground: cssVar("--color-surface", "#fff"),
      },
    });

    sequence += 1;
    // The `wq-mermaid-` prefix is referenced by the reduced-motion exclusion in
    // styles/theme.css — Mermaid measures inside `#d<id>` on <body>.
    mermaid
      .render(`wq-mermaid-${baseId}-${sequence}`, chart)
      .then(({ svg }) => {
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = svg;
        const el = containerRef.current.querySelector("svg");
        if (el) {
          // Mermaid hands back width="100%", which blows small diagrams up to
          // the panel width. Fall back to the viewBox size and scale down only
          // when the diagram is wider than the panel.
          const viewBox = el.getAttribute("viewBox")?.split(/\s+/) ?? [];
          const naturalWidth = Number(viewBox[2]);
          el.removeAttribute("width");
          el.removeAttribute("height");
          el.style.width = Number.isFinite(naturalWidth) ? `${naturalWidth}px` : "100%";
          el.style.maxWidth = "100%";
          el.style.height = "auto";
          if (ariaLabel) el.setAttribute("aria-label", ariaLabel);
        }
        setReady(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t("mermaid.renderError"));
        setReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, [chart, theme, baseId, ariaLabel, t]);

  if (error) {
    return <ErrorState error={new Error(error)} title={t("mermaid.failed")} />;
  }

  return (
    <div dir="ltr" className={cn("relative w-full overflow-x-auto scroll-thin", className)}>
      {!ready ? <Skeleton className="h-52 w-full" /> : null}
      <div
        ref={containerRef}
        role="img"
        aria-label={ariaLabel}
        className="mermaid-host flex justify-center"
      />
    </div>
  );
}
