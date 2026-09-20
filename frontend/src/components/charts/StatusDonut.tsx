import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { CaseStatus, DashboardCharts } from "@/lib/types";
import { CASE_STATUS_LABEL } from "@/lib/constants";
import { formatNumber } from "@/lib/format";
import { tooltipStyles } from "./ChartTooltip";
import { useChartPalette } from "./chartTheme";

export function StatusDonut({ data }: { data: DashboardCharts["status_split"] }) {
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);

  const colourFor: Record<CaseStatus, string> = {
    intake: palette.ink2,
    processing: palette.info,
    needs_review: palette.warning,
    in_review: palette.accent,
    approved: palette.success,
    posting: palette.info,
    completed: palette.primary,
    rejected: palette.danger,
    failed: palette.danger,
  };

  const rows = data.map((d) => ({
    name: CASE_STATUS_LABEL[d.status],
    value: d.count,
    fill: colourFor[d.status],
  }));
  const total = rows.reduce((sum, r) => sum + r.value, 0);

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="relative h-44 w-full sm:w-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke={palette.surface}
              strokeWidth={2}
            >
              {rows.map((row) => (
                <Cell key={row.name} fill={row.fill} />
              ))}
            </Pie>
            <Tooltip {...styles} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-h1 font-semibold text-ink tabular">{formatNumber(total)}</span>
          <span className="label-caption text-ink-2">cases</span>
        </div>
      </div>
      <ul className="flex-1 space-y-1.5">
        {rows.map((row) => (
          <li key={row.name} className="flex items-center gap-2 text-small">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: row.fill }}
              aria-hidden
            />
            <span className="truncate text-ink-2">{row.name}</span>
            <span className="ms-auto font-semibold text-ink tabular">
              {formatNumber(row.value)}
            </span>
            <span className="w-11 text-end text-caption text-ink-2 tabular">
              {total ? `${Math.round((row.value / total) * 100)}%` : "—"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
