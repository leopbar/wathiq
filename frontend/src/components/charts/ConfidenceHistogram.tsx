import { Bar, BarChart, Cell, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardCharts } from "@/lib/types";
import { axisProps, tooltipStyles } from "./ChartTooltip";
import { chartMargin, useChartPalette } from "./chartTheme";

/** Bucket labels look like "0.7–0.8"; colour follows the confidence bands. */
function bucketTone(bucket: string): "low" | "medium" | "high" {
  const start = Number.parseFloat(bucket);
  if (Number.isNaN(start)) return "medium";
  if (start >= 0.9) return "high";
  if (start >= 0.7) return "medium";
  return "low";
}

export function ConfidenceHistogram({ data }: { data: DashboardCharts["confidence_histogram"] }) {
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);
  const tone = { low: palette.danger, medium: palette.warning, high: palette.success };

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={chartMargin}>
        <CartesianGrid vertical={false} stroke={palette.grid} strokeDasharray="3 3" />
        <XAxis dataKey="bucket" {...axisProps(palette)} />
        <YAxis allowDecimals={false} width={40} {...axisProps(palette)} />
        <Tooltip {...styles} />
        <Bar dataKey="count" name="Fields" radius={[4, 4, 0, 0]} maxBarSize={44}>
          {data.map((row) => (
            <Cell key={row.bucket} fill={tone[bucketTone(row.bucket)]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
