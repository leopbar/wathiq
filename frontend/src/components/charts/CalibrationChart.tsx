import {
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ComposedChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { useTranslation } from "react-i18next";
import type { QualityCalibration } from "@/lib/types";
import { formatPercent } from "@/lib/format";
import { axisProps, tooltipStyles } from "./ChartTooltip";
import { useChartPalette } from "./chartTheme";

export function CalibrationChart({ data }: { data: QualityCalibration }) {
  const { t } = useTranslation();
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);
  const samples = t("charts.samples");

  const points = data.points.map((p) => ({ ...p, perfect: p.predicted }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
        <CartesianGrid stroke={palette.grid} strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="predicted"
          domain={[0, 1]}
          ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
          tickFormatter={(v: number) => formatPercent(v)}
          name={t("charts.predicted")}
          {...axisProps(palette)}
        />
        <YAxis
          type="number"
          dataKey="observed"
          domain={[0, 1]}
          ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
          tickFormatter={(v: number) => formatPercent(v)}
          name={t("charts.observed")}
          width={48}
          {...axisProps(palette)}
        />
        <ZAxis type="number" dataKey="n" range={[40, 260]} name={samples} />
        <Tooltip
          {...styles}
          formatter={(value: unknown, name: unknown) =>
            (name === samples
              ? [String(value), String(name)]
              : [formatPercent(Number(value), 1), String(name)]) as [string, string]
          }
        />
        <Legend
          iconSize={10}
          wrapperStyle={{ fontSize: 12, color: palette.ink2, paddingTop: 6 }}
        />
        <Line
          type="linear"
          dataKey="perfect"
          name={t("charts.perfectCalibration")}
          stroke={palette.ink2}
          strokeDasharray="5 4"
          strokeWidth={1.5}
          dot={false}
          activeDot={false}
          legendType="plainline"
        />
        <Scatter name={t("charts.observedAccuracy")} dataKey="observed" fill={palette.primary} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
