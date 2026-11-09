import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PlayerSeasonCaOps } from "../types/playerSeasonCaOps";
import {
  MINIMUM_PLATE_APPEARANCES,
  bottomPlayersByCaOps,
  topNegativeCaOpsAdjustments,
  topPlayersByCaOps,
  topPositiveCaOpsAdjustments,
  type ComparableCaOpsRow,
} from "./caOpsAnalyticsRankings";

interface RankedPoint {
  full_name: string;
  observed_ops: number | null;
  ca_ops: number;
  adjustment: number | null;
  adjustmentLabel: string;
}

function formatOps(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

function formatSigned(value: number): string {
  const formatted = value.toFixed(3);
  return value > 0 ? `+${formatted}` : formatted;
}

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

function toRankedPoints(rows: PlayerSeasonCaOps[]): RankedPoint[] {
  return rows.flatMap((row) => {
    if (row.ca_ops === null) {
      return [];
    }
    return [
      {
        full_name: row.full_name,
        observed_ops: row.observed_ops,
        ca_ops: row.ca_ops,
        adjustment: null,
        adjustmentLabel: "",
      },
    ];
  });
}

function comparableToPoints(rows: ComparableCaOpsRow[]): RankedPoint[] {
  return rows.map((row) => {
    const adjustment = row.ca_ops - row.observed_ops;
    return {
      full_name: row.full_name,
      observed_ops: row.observed_ops,
      ca_ops: row.ca_ops,
      adjustment,
      adjustmentLabel: formatSigned(adjustment),
    };
  });
}

function RankedTooltip({
  active,
  payload,
  showAdjustment,
}: {
  active?: boolean;
  payload?: { payload: RankedPoint }[];
  showAdjustment: boolean;
}) {
  if (!active || payload === undefined || payload[0] === undefined) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-player">{point.full_name}</p>
      <p>Observed OPS: {formatOps(point.observed_ops)}</p>
      <p>CA-OPS: {formatOps(point.ca_ops)}</p>
      {showAdjustment && point.adjustment !== null ? (
        <p>Adjustment: {formatSigned(point.adjustment)}</p>
      ) : null}
    </div>
  );
}

function RankedCaOpsBarChart({
  data,
  showAdjustment,
  ariaLabel,
}: {
  data: RankedPoint[];
  showAdjustment: boolean;
  ariaLabel: string;
}) {
  const tickStyle = { fill: "var(--color-muted)", fontSize: 12 };
  const height = Math.max(280, data.length * 44 + 96);

  return (
    <div className="ca-ops-ranked-chart" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: showAdjustment ? 56 : 24, left: 8, bottom: 8 }}
          barCategoryGap="28%"
          barGap={4}
        >
          <CartesianGrid
            stroke="var(--color-chart-grid)"
            strokeDasharray="3 3"
          />
          <XAxis
            type="number"
            tick={tickStyle}
            tickFormatter={(value: number) => formatOps(value)}
            domain={[0, "auto"]}
          />
          <YAxis
            type="category"
            dataKey="full_name"
            width={148}
            tick={tickStyle}
            interval={0}
            reversed
          />
          <Tooltip content={<RankedTooltip showAdjustment={showAdjustment} />} />
          <Legend wrapperStyle={{ color: "var(--color-text)", fontSize: 12 }} />
          <Bar
            dataKey="observed_ops"
            name="Observed OPS"
            fill="var(--color-chart-rolling)"
            maxBarSize={22}
            shape={omitNullBar}
          />
          <Bar
            dataKey="ca_ops"
            name="CA-OPS"
            fill="var(--color-chart-season)"
            maxBarSize={22}
            shape={omitNullBar}
          >
            {showAdjustment ? (
              <LabelList
                dataKey="adjustmentLabel"
                position="right"
                fill="var(--color-muted)"
                fontSize={11}
              />
            ) : null}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartSection({
  title,
  explanation,
  children,
  emptyMessage,
  hasData,
}: {
  title: string;
  explanation: string;
  children: ReactNode;
  emptyMessage: string;
  hasData: boolean;
}) {
  return (
    <section className="chart-panel ca-ops-dashboard-panel">
      <h3>{title}</h3>
      <p className="chart-explanation">{explanation}</p>
      {hasData ? (
        children
      ) : (
        <p className="status chart-unavailable">{emptyMessage}</p>
      )}
    </section>
  );
}

interface CaOpsAnalyticsChartsProps {
  players: PlayerSeasonCaOps[];
}

export function CaOpsAnalyticsCharts({ players }: CaOpsAnalyticsChartsProps) {
  const topCaOps = toRankedPoints(topPlayersByCaOps(players));
  const bottomCaOps = toRankedPoints(bottomPlayersByCaOps(players));
  const positiveAdjustments = comparableToPoints(
    topPositiveCaOpsAdjustments(players),
  );
  const negativeAdjustments = comparableToPoints(
    topNegativeCaOpsAdjustments(players),
  );

  return (
    <div className="ca-ops-dashboard-charts">
      <ChartSection
        title="Top 10 Players by CA-OPS"
        explanation="This chart compares each player's Observed OPS with their Competition-Adjusted OPS (CA-OPS). A difference between the two shows how the quality of opposing pitchers affected the player's adjusted result."
        hasData={topCaOps.length > 0}
        emptyMessage={`No players with at least ${MINIMUM_PLATE_APPEARANCES} plate appearances have a usable CA-OPS for this season.`}
      >
        <RankedCaOpsBarChart
          data={topCaOps}
          showAdjustment={false}
          ariaLabel="Top 10 players by CA-OPS"
        />
      </ChartSection>
      <ChartSection
        title="Top 10 Largest Positive CA-OPS Adjustments"
        explanation="This chart shows the players whose CA-OPS increased the most compared with their Observed OPS. A positive adjustment generally indicates that the hitter faced stronger-than-average pitching relative to the league baseline."
        hasData={positiveAdjustments.length > 0}
        emptyMessage={`No players with at least ${MINIMUM_PLATE_APPEARANCES} plate appearances have a positive CA-OPS adjustment for this season.`}
      >
        <RankedCaOpsBarChart
          data={positiveAdjustments}
          showAdjustment
          ariaLabel="Top 10 largest positive CA-OPS adjustments"
        />
      </ChartSection>
      <ChartSection
        title="Bottom 10 Players by CA-OPS"
        explanation="This chart compares Observed OPS with CA-OPS for the players with the lowest Competition-Adjusted OPS. The difference between the two reflects the adjustment for the quality of opposing pitchers faced."
        hasData={bottomCaOps.length > 0}
        emptyMessage={`No players with at least ${MINIMUM_PLATE_APPEARANCES} plate appearances have a usable CA-OPS for this season.`}
      >
        <RankedCaOpsBarChart
          data={bottomCaOps}
          showAdjustment={false}
          ariaLabel="Bottom 10 players by CA-OPS"
        />
      </ChartSection>
      <ChartSection
        title="Top 10 Largest Negative CA-OPS Adjustments"
        explanation="This chart shows the players whose CA-OPS decreased the most compared with their Observed OPS. A negative CA-OPS adjustment can indicate that the hitter's observed performance came against weaker-than-average pitching relative to the league baseline."
        hasData={negativeAdjustments.length > 0}
        emptyMessage={`No players with at least ${MINIMUM_PLATE_APPEARANCES} plate appearances have a negative CA-OPS adjustment for this season.`}
      >
        <RankedCaOpsBarChart
          data={negativeAdjustments}
          showAdjustment
          ariaLabel="Top 10 largest negative CA-OPS adjustments"
        />
      </ChartSection>
    </div>
  );
}
