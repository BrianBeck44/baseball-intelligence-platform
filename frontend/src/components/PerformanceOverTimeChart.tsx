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

import type { PlayerGameRecord } from "../types/playerGames";

interface ChartPoint {
  pointId: string;
  game_date: string;
  rolling_14_ops: number | null;
  season_ops: number | null;
}

function toChartPoints(games: PlayerGameRecord[]): ChartPoint[] {
  return games.map((game, index) => ({
    pointId: `${game.game_id}-${game.team_id}-${index}`,
    game_date: game.game_date,
    rolling_14_ops: game.rolling_14_ops,
    season_ops: game.season_ops,
  }));
}

function formatOps(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

interface PerformanceOverTimeChartProps {
  games: PlayerGameRecord[];
}

export function PerformanceOverTimeChart({
  games,
}: PerformanceOverTimeChartProps) {
  const data = toChartPoints(games);
  const tickStyle = { fill: "var(--color-muted)", fontSize: 12 };
  const tooltipStyle = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  };

  return (
    <div className="chart-panel" aria-label="OPS over time">
      <h3>OPS over time</h3>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 4, bottom: 8 }}
        >
          <CartesianGrid stroke="var(--color-chart-grid)" strokeDasharray="3 3" />
          <XAxis
            dataKey="pointId"
            tickFormatter={(_value, index) => data[index]?.game_date ?? ""}
            interval="preserveStartEnd"
            minTickGap={28}
            tick={tickStyle}
          />
          <YAxis
            label={{
              value: "OPS",
              angle: -90,
              position: "insideLeft",
              fill: "var(--color-muted)",
            }}
            tick={tickStyle}
            tickFormatter={(value: number) => value.toFixed(3)}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={{ color: "var(--color-text)" }}
            itemStyle={{ color: "var(--color-text)" }}
            labelFormatter={(_label, payload) => {
              const point = payload?.[0]?.payload as ChartPoint | undefined;
              return point?.game_date ?? "";
            }}
            formatter={(value, name) => [
              formatOps(value),
              String(name),
            ]}
          />
          <Legend wrapperStyle={{ color: "var(--color-text)" }} />
          <Line
            type="monotone"
            dataKey="rolling_14_ops"
            name="Rolling 14 OPS"
            stroke="var(--color-chart-rolling)"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="season_ops"
            name="Season OPS"
            stroke="var(--color-chart-season)"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
