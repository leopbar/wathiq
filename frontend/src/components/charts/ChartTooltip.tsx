import type { CSSProperties } from "react";
import type { ChartPalette } from "./chartTheme";

/**
 * Recharts renders its tooltip outside our CSS cascade, so the theme tokens are
 * handed over as inline styles instead of classes.
 */
export function tooltipStyles(palette: ChartPalette): {
  contentStyle: CSSProperties;
  labelStyle: CSSProperties;
  itemStyle: CSSProperties;
  cursor: { fill: string };
} {
  return {
    contentStyle: {
      background: palette.surface,
      border: `1px solid ${palette.border}`,
      borderRadius: 8,
      boxShadow: "0 4px 12px rgb(0 0 0 / 0.12)",
      fontSize: 12,
      padding: "8px 10px",
    },
    labelStyle: { color: palette.ink, fontWeight: 600, marginBottom: 2 },
    itemStyle: { color: palette.ink2, padding: 0 },
    cursor: { fill: `${palette.grid}66` },
  };
}

export const axisProps = (palette: ChartPalette) => ({
  stroke: palette.grid,
  tick: { fill: palette.ink2, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: palette.grid },
});
