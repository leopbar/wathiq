import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import type { DashboardCharts } from "@/lib/types";
import { formatDate } from "@/lib/format";
import { axisProps, tooltipStyles } from "./ChartTooltip";
import { chartMargin, useChartPalette } from "./chartTheme";

export function VolumeChart({ data }: { data: DashboardCharts["volume_by_day"] }) {
  const { t } = useTranslation();
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={chartMargin}>
        <defs>
          <linearGradient id="wq-straight" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={palette.primary} stopOpacity={0.55} />
            <stop offset="100%" stopColor={palette.primary} stopOpacity={0.06} />
          </linearGradient>
          <linearGradient id="wq-reviewed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={palette.warning} stopOpacity={0.5} />
            <stop offset="100%" stopColor={palette.warning} stopOpacity={0.06} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={palette.grid} strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={(v: string) => formatDate(v, "d MMM")} {...axisProps(palette)} />
        <YAxis allowDecimals={false} width={40} {...axisProps(palette)} />
        <Tooltip
          {...styles}
          labelFormatter={(label: unknown) =>
            formatDate(typeof label === "string" ? label : null, "d MMM yyyy")
          }
          cursor={{ stroke: palette.grid }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, color: palette.ink2, paddingTop: 8 }}
        />
        <Area
          type="monotone"
          dataKey="straight_through"
          name={t("dashboard.straightThrough")}
          stackId="1"
          stroke={palette.primary}
          fill="url(#wq-straight)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="reviewed"
          name={t("dashboard.humanReviewed")}
          stackId="1"
          stroke={palette.warning}
          fill="url(#wq-reviewed)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
