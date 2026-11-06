import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PlayerSeasonBatting } from "../types/playerSeasonBatting";
import type { PlayerSeasonCaOps } from "../types/playerSeasonCaOps";

const CA_OPS_METRICS: {
  key: keyof Pick<
    PlayerSeasonCaOps,
    "observed_ops" | "league_ops" | "expected_opponent_ops" | "ca_ops"
  >;
  label: string;
}[] = [
  { key: "observed_ops", label: "Observed OPS" },
  { key: "league_ops", label: "League OPS" },
  { key: "expected_opponent_ops", label: "Expected OPS" },
  { key: "ca_ops", label: "CA-OPS" },
];

function omitNullBar(props: {
  value?: number | string | null;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
}) {
  if (
    typeof props.value !== "number" ||
    props.x == null ||
    props.y == null ||
    props.width == null ||
    props.height == null
  ) {
    return <g />;
  }
  return (
    <rect
      x={props.x}
      y={props.y}
      width={props.width}
      height={props.height}
      fill={props.fill}
    />
  );
}

type ChartFormat = "average" | "count";

interface ComparisonBarPoint {
  metric: string;
  player1: number | null;
  player2: number | null;
}

function formatAverage(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

function formatCount(value: unknown): string {
  return typeof value === "number" ? String(Math.round(value)) : "—";
}

function formatValue(value: unknown, format: ChartFormat): string {
  return format === "average" ? formatAverage(value) : formatCount(value);
}

function missingNames(
  firstName: string,
  secondName: string,
  firstValue: number | null,
  secondValue: number | null,
): string[] {
  const names: string[] = [];
  if (firstValue === null) {
    names.push(firstName);
  }
  if (secondValue === null) {
    names.push(secondName);
  }
  return names;
}

interface PlayerComparisonBarChartProps {
  title: string;
  metric: string;
  yLabel: string;
  firstName: string;
  secondName: string;
  firstValue: number | null;
  secondValue: number | null;
  format: ChartFormat;
}

function PlayerComparisonBarChart({
  title,
  metric,
  yLabel,
  firstName,
  secondName,
  firstValue,
  secondValue,
  format,
}: PlayerComparisonBarChartProps) {
  const unavailable = missingNames(
    firstName,
    secondName,
    firstValue,
    secondValue,
  );
  const tickStyle = { fill: "var(--color-muted)", fontSize: 12 };
  const tooltipStyle = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  };
  const data: ComparisonBarPoint[] = [
    {
      metric,
      player1: firstValue,
      player2: secondValue,
    },
  ];

  return (
    <div className="chart-panel" aria-label={title}>
      <h3>{title}</h3>
      {unavailable.length === 2 ? (
        <p className="status chart-unavailable">
          {metric} unavailable for {unavailable.join(" and ")}.
        </p>
      ) : (
        <>
          {unavailable.length === 1 ? (
            <p className="status">
              {metric} unavailable for {unavailable[0]}.
            </p>
          ) : null}
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={data}
              margin={{ top: 8, right: 8, left: 4, bottom: 8 }}
              barCategoryGap="35%"
              barGap={6}
              maxBarSize={48}
            >
              <CartesianGrid
                stroke="var(--color-chart-grid)"
                strokeDasharray="3 3"
              />
              <XAxis dataKey="metric" tick={tickStyle} />
              <YAxis
                domain={[0, "auto"]}
                allowDecimals={format === "average"}
                label={{
                  value: yLabel,
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--color-muted)",
                }}
                tick={tickStyle}
                tickFormatter={(value: number) => formatValue(value, format)}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={{ color: "var(--color-text)" }}
                itemStyle={{ color: "var(--color-text)" }}
                formatter={(value, name) => [
                  formatValue(value, format),
                  String(name),
                ]}
              />
              <Legend wrapperStyle={{ color: "var(--color-text)", fontSize: 12 }} />
              <Bar
                dataKey="player1"
                name={firstName}
                fill="var(--color-chart-rolling)"
                maxBarSize={48}
              />
              <Bar
                dataKey="player2"
                name={secondName}
                fill="var(--color-chart-season)"
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}

interface PlayerComparisonChartsProps {
  first: PlayerSeasonBatting;
  second: PlayerSeasonBatting;
}

export function PlayerComparisonCharts({
  first,
  second,
}: PlayerComparisonChartsProps) {
  return (
    <div
      className="comparison-charts"
      key={`${first.player_id}-${second.player_id}-${first.season_id}`}
    >
      <PlayerComparisonBarChart
        title="OPS"
        metric="OPS"
        yLabel="OPS"
        firstName={first.full_name}
        secondName={second.full_name}
        firstValue={first.ops}
        secondValue={second.ops}
        format="average"
      />
      <PlayerComparisonBarChart
        title="Batting Average (AVG)"
        metric="AVG"
        yLabel="AVG"
        firstName={first.full_name}
        secondName={second.full_name}
        firstValue={first.batting_average}
        secondValue={second.batting_average}
        format="average"
      />
      <PlayerComparisonBarChart
        title="Home Runs (HR)"
        metric="HR"
        yLabel="HR"
        firstName={first.full_name}
        secondName={second.full_name}
        firstValue={first.home_runs}
        secondValue={second.home_runs}
        format="count"
      />
    </div>
  );
}

interface PlayerCaOpsComparisonChartProps {
  first: PlayerSeasonCaOps;
  second: PlayerSeasonCaOps;
}

export function PlayerCaOpsComparisonChart({
  first,
  second,
}: PlayerCaOpsComparisonChartProps) {
  const data = CA_OPS_METRICS.map((metric) => ({
    metric: metric.label,
    player1: first[metric.key],
    player2: second[metric.key],
  })).filter((point) => point.player1 !== null || point.player2 !== null);
  const tickStyle = { fill: "var(--color-muted)", fontSize: 12 };
  const tooltipStyle = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  };

  if (data.length === 0) {
    return (
      <div className="chart-panel" aria-label="CA-OPS comparison">
        <h3>CA-OPS</h3>
        <p className="status chart-unavailable">
          CA-OPS unavailable for {first.full_name} and {second.full_name}.
        </p>
      </div>
    );
  }

  return (
    <div
      className="chart-panel ca-ops-chart"
      aria-label="CA-OPS comparison"
      key={`${first.player_id}-${second.player_id}-${first.season_id}`}
    >
      <h3>CA-OPS</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: 4, bottom: 8 }}
          barCategoryGap="28%"
          barGap={6}
          maxBarSize={48}
        >
          <CartesianGrid
            stroke="var(--color-chart-grid)"
            strokeDasharray="3 3"
          />
          <XAxis dataKey="metric" tick={tickStyle} interval={0} />
          <YAxis
            domain={["auto", "auto"]}
            allowDecimals
            label={{
              value: "OPS",
              angle: -90,
              position: "insideLeft",
              fill: "var(--color-muted)",
            }}
            tick={tickStyle}
            tickFormatter={(value: number) => formatAverage(value)}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={{ color: "var(--color-text)" }}
            itemStyle={{ color: "var(--color-text)" }}
            formatter={(value, name) => [
              formatAverage(value),
              String(name),
            ]}
          />
          <Legend wrapperStyle={{ color: "var(--color-text)", fontSize: 12 }} />
          <Bar
            dataKey="player1"
            name={first.full_name}
            fill="var(--color-chart-rolling)"
            maxBarSize={48}
            shape={omitNullBar}
          />
          <Bar
            dataKey="player2"
            name={second.full_name}
            fill="var(--color-chart-season)"
            maxBarSize={48}
            shape={omitNullBar}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
