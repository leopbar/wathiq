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
import type { QualityCalibration } from "@/lib/types";
import { axisProps, tooltipStyles } from "./ChartTooltip";
import { useChartPalette } from "./chartTheme";

export function CalibrationChart({ data }: { data: QualityCalibration }) {
  const palette = useChartPalette();
  const styles = tooltipStyles(palette);

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
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
          name="Predicted"
          {...axisProps(palette)}
        />
        <YAxis
          type="number"
          dataKey="observed"
          domain={[0, 1]}
          ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
          name="Observed"
          width={48}
          {...axisProps(palette)}
        />
        <ZAxis type="number" dataKey="n" range={[40, 260]} name="Samples" />
        <Tooltip
          {...styles}
          formatter={(value: unknown, name: unknown) =>
            (name === "Samples"
              ? [String(value), String(name)]
              : [`${(Number(value) * 100).toFixed(1)}%`, String(name)]) as [string, string]
          }
        />
        <Legend
          iconSize={10}
          wrapperStyle={{ fontSize: 12, color: palette.ink2, paddingTop: 6 }}
        />
        <Line
          type="linear"
          dataKey="perfect"
          name="Perfect calibration"
          stroke={palette.ink2}
          strokeDasharray="5 4"
          strokeWidth={1.5}
          dot={false}
          activeDot={false}
          legendType="plainline"
        />
        <Scatter name="Observed accuracy" dataKey="observed" fill={palette.primary} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
