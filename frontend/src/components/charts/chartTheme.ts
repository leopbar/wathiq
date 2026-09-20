import { useMemo } from "react";
import { cssVar, useTheme } from "@/components/useTheme";

export interface ChartPalette {
  ink: string;
  ink2: string;
  grid: string;
  surface: string;
  border: string;
  primary: string;
  accent: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  series: string[];
}

/** Recharts takes literal colours, so read the active theme tokens each flip. */
export function useChartPalette(): ChartPalette {
  const { theme } = useTheme();

  return useMemo(() => {
    const primary = cssVar("--color-primary", "#0e5e5a");
    const info = cssVar("--color-info", "#1d4ed8");
    const accent = cssVar("--color-accent", "#b58b2a");
    const success = cssVar("--color-success", "#0f7a52");
    const warning = cssVar("--color-warning", "#a65f17");
    const danger = cssVar("--color-danger", "#b3261e");

    return {
      ink: cssVar("--color-ink", "#0b1220"),
      ink2: cssVar("--color-ink-2", "#5a6675"),
      grid: cssVar("--color-border", "#e3e7ee"),
      surface: cssVar("--color-surface", "#ffffff"),
      border: cssVar("--color-border", "#e3e7ee"),
      primary,
      accent,
      success,
      warning,
      danger,
      info,
      series: [primary, info, accent, success, warning, danger],
    };
    // `theme` is the invalidation signal, not a value we read directly.
  }, [theme]);
}

export const chartMargin = { top: 8, right: 8, bottom: 0, left: -12 };
