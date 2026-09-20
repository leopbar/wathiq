import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardCharts } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/format";
import { axisProps, tooltipStyles } from "./ChartTooltip";
import { chartMargin, useChartPalette } from "./chartTheme";

export function HandlingTimeChart({ data }: { data: DashboardCharts["handling_time_by_day"] }) {
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={chartMargin}>
        <CartesianGrid vertical={false} stroke={palette.grid} strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tickFormatter={(v: string) => formatDate(v, "d MMM")}
          {...axisProps(palette)}
        />
        <YAxis
          width={56}
          tickFormatter={(v: number) => formatDuration(v)}
          {...axisProps(palette)}
        />
        <Tooltip
          {...styles}
          labelFormatter={(label: unknown) =>
            formatDate(typeof label === "string" ? label : null, "d MMM yyyy")
          }
          formatter={(value: unknown, name: unknown) =>
            [formatDuration(Number(value)), String(name)] as [string, string]
          }
        />
        <Legend
          iconType="plainline"
          iconSize={14}
          wrapperStyle={{ fontSize: 12, color: palette.ink2, paddingTop: 8 }}
        />
        <Line
          type="monotone"
          dataKey="p50_ms"
          name="p50"
          stroke={palette.primary}
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="p90_ms"
          name="p90"
          stroke={palette.accent}
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
