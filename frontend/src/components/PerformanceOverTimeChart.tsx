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

  return (
    <div className="chart-panel" aria-label="OPS over time">
      <h3>OPS over time</h3>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 4, bottom: 8 }}
        >
          <CartesianGrid stroke="#d8dee3" strokeDasharray="3 3" />
          <XAxis
            dataKey="pointId"
            tickFormatter={(_value, index) => data[index]?.game_date ?? ""}
            interval="preserveStartEnd"
            minTickGap={28}
            tick={{ fill: "#3d4f5c", fontSize: 12 }}
          />
          <YAxis
            label={{
              value: "OPS",
              angle: -90,
              position: "insideLeft",
              fill: "#3d4f5c",
            }}
            tick={{ fill: "#3d4f5c", fontSize: 12 }}
            tickFormatter={(value: number) => value.toFixed(3)}
          />
          <Tooltip
            labelFormatter={(_label, payload) => {
              const point = payload?.[0]?.payload as ChartPoint | undefined;
              return point?.game_date ?? "";
            }}
            formatter={(value, name) => [
              formatOps(value),
              String(name),
            ]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="rolling_14_ops"
            name="Rolling 14 OPS"
            stroke="#123d2a"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="season_ops"
            name="Season OPS"
            stroke="#8a5a12"
            strokeWidth={2}
            connectNulls={false}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
