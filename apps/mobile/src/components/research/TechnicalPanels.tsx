import { useMemo, useState } from "react";
import { Text, View } from "react-native";
import Svg, { Line, Path, Rect } from "react-native-svg";
import { formatMarketDate } from "../../dateFormat";
import {
  compactTrend,
  describeLatest,
  describeTrend,
  latestSeriesValue,
} from "../../research/chartLabels";
import type { MacroChart, SeriesPoint } from "../../research/chartMath";
import {
  calculateMacd,
  calculateRsi,
  calculateVolatility,
  chartBarScaleMaximum,
  chartScale,
  formatMacroValue,
  macroChart,
  seriesTrend,
  simpleMovingAverage,
  technicalPath,
} from "../../research/chartMath";
import { colors, palette, appStyles as styles } from "../../theme";
import type { StockBundle, TechnicalIndicators } from "../../types";
import { SectionHeader } from "../common";
import { workspaceStyles } from "./researchStyles";

export function TechnicalPanels({
  prices,
  availability,
  chartColumns,
}: {
  prices: StockBundle["prices"];
  availability: TechnicalIndicators["availability"];
  chartColumns: 1 | 2;
}) {
  const data = useMemo(() => {
    const closes = prices.map((point) => point.close);
    const toPoints = (values: Array<number | null>): SeriesPoint[] =>
      values.map((value, index) => ({ date: prices[index].date, value }));
    const { macd, signal } = calculateMacd(closes);
    return {
      ma20: toPoints(simpleMovingAverage(closes, 20)),
      ma50: toPoints(simpleMovingAverage(closes, 50)),
      rsi: toPoints(calculateRsi(closes)),
      macd: toPoints(macd),
      macdSignal: toPoints(signal),
      histogram: toPoints(
        macd.map((value, index) =>
          value === null || signal[index] === null ? null : value - signal[index],
        ),
      ),
      volume: prices.map((point) => ({
        date: point.date,
        value: point.volume,
      })),
      volatility: toPoints(calculateVolatility(closes)),
    };
  }, [prices]);
  const hasAvailableSeries = Boolean(availability && Object.values(availability).some(Boolean));
  const latestDate = hasAvailableSeries ? prices[prices.length - 1]?.date : null;
  return (
    <View style={styles.technicalPanels}>
      <SectionHeader title="Technical panels" />
      <Text style={workspaceStyles.sectionDate}>
        {latestDate ? `As of ${formatMarketDate(latestDate)}` : "Daily history unavailable"}
      </Text>
      <ResponsiveChartGrid columns={chartColumns}>
        <ChartGridItem columns={chartColumns}>
          {availability?.moving_average_20 || availability?.moving_average_50 ? (
            <TechnicalLineChart
              title="Moving averages"
              subtitle="Daily closes"
              series={[
                ...(availability.moving_average_20
                  ? [{ label: "MA20", color: palette.bull, points: data.ma20 }]
                  : []),
                ...(availability.moving_average_50
                  ? [
                      {
                        label: "MA50",
                        color: palette.signal,
                        points: data.ma50,
                      },
                    ]
                  : []),
              ]}
            />
          ) : (
            <ChartEmptyState
              title="Moving averages"
              message="MA20 and MA50 need labelled daily history before they can be shown."
            />
          )}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.rsi ? (
            <TechnicalLineChart
              title="Relative strength"
              subtitle="RSI 14 · 30/70 bands"
              series={[
                {
                  label: "RSI",
                  color: colors.chart.oscillator,
                  points: data.rsi,
                },
              ]}
              references={[30, 70]}
              fixedDomain={[0, 100]}
            />
          ) : (
            <ChartEmptyState
              title="Relative strength"
              message="RSI needs labelled daily history before it can be shown."
            />
          )}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.macd || availability?.macd_signal ? (
            <MacdChart
              macd={
                availability.macd
                  ? data.macd
                  : data.macd.map((point) => ({ ...point, value: null }))
              }
              signal={
                availability.macd_signal
                  ? data.macdSignal
                  : data.macdSignal.map((point) => ({ ...point, value: null }))
              }
              histogram={
                availability.macd && availability.macd_signal
                  ? data.histogram
                  : data.histogram.map((point) => ({ ...point, value: null }))
              }
            />
          ) : (
            <ChartEmptyState
              title="MACD"
              message="MACD and its signal line need labelled daily history before they can be shown."
            />
          )}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.volume ? (
            <TechnicalBarChart
              title="Daily volume"
              subtitle="Shares traded"
              points={data.volume}
              color={colors.chart.volume}
            />
          ) : (
            <ChartEmptyState
              title="Daily volume"
              message="Volume needs labelled daily history before it can be shown."
            />
          )}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.volatility ? (
            <TechnicalLineChart
              title="Annualised volatility"
              subtitle="20-day realised"
              series={[
                {
                  label: "Volatility",
                  color: palette.bear,
                  points: data.volatility,
                },
              ]}
              suffix="%"
            />
          ) : (
            <ChartEmptyState
              title="Annualised volatility"
              message="Volatility needs labelled daily history before it can be shown."
            />
          )}
        </ChartGridItem>
      </ResponsiveChartGrid>
    </View>
  );
}

export function MacroContextPanel({
  ticker,
  context,
  chartColumns,
}: {
  ticker: string;
  context: StockBundle["macro_context"];
  chartColumns: 1 | 2;
}) {
  const charts = useMemo(
    () => ({
      sp500: macroChart(context, "sp500", "S&P 500"),
      vix: macroChart(context, "vix", "VIX"),
      effectiveRate: macroChart(context, "effective_fed_funds_rate", "Effective rate"),
      twoYear: macroChart(context, "treasury_2y_yield", "2Y"),
      tenYear: macroChart(context, "treasury_10y_yield", "10Y"),
      thirtyYear: macroChart(context, "treasury_30y_yield", "30Y"),
      wti: macroChart(context, "wti_spot", "WTI crude"),
    }),
    [context],
  );
  if (!Object.values(charts).some(Boolean)) return null;
  const rateSeries = [
    charts.effectiveRate,
    charts.twoYear,
    charts.tenYear,
    charts.thirtyYear,
  ].filter((chart): chart is MacroChart => chart !== null);
  const rateDate = rateSeries
    .map((chart) => chart.latest.date)
    .sort()
    .at(-1);

  return (
    <View style={styles.macroSection}>
      <SectionHeader title="Market backdrop" />
      <View style={styles.macroDisclosure}>
        <Text style={styles.macroDisclosureText}>
          {Object.values(charts).some((chart) => chart?.simulated)
            ? "Simulated context · not market data"
            : `Market context only · does not explain ${ticker} price moves`}
        </Text>
      </View>
      <ResponsiveChartGrid columns={chartColumns}>
        {charts.sp500 ? (
          <ChartGridItem columns={chartColumns}>
            <TechnicalLineChart
              title={`${charts.sp500.label} · ${formatMacroValue(charts.sp500.latest.value ?? 0, charts.sp500.unit)}`}
              subtitle={`As of ${formatMarketDate(charts.sp500.latest.date)}`}
              series={[
                {
                  label: charts.sp500.label,
                  color: colors.chart.positive,
                  points: charts.sp500.points,
                },
              ]}
              showTrend={false}
            />
          </ChartGridItem>
        ) : null}
        {charts.vix ? (
          <ChartGridItem columns={chartColumns}>
            <TechnicalLineChart
              title={`${charts.vix.label} · ${formatMacroValue(charts.vix.latest.value ?? 0, charts.vix.unit)}`}
              subtitle={`As of ${formatMarketDate(charts.vix.latest.date)}`}
              series={[
                {
                  label: charts.vix.label,
                  color: colors.chart.oscillator,
                  points: charts.vix.points,
                },
              ]}
              showTrend={false}
            />
          </ChartGridItem>
        ) : null}
        {rateSeries.length ? (
          <ChartGridItem columns={chartColumns}>
            <TechnicalLineChart
              title="U.S. rates"
              subtitle={`As of ${formatMarketDate(rateDate)}`}
              series={rateSeries.map((chart, index) => ({
                label: chart.label,
                color: [
                  colors.action.primary,
                  colors.chart.volume,
                  colors.chart.positive,
                  colors.chart.oscillator,
                ][index],
                points: chart.points,
              }))}
              suffix="%"
              showTrend={false}
              showValuesInLegend
            />
          </ChartGridItem>
        ) : null}
        {charts.wti ? (
          <ChartGridItem columns={chartColumns}>
            <TechnicalLineChart
              title={`${charts.wti.label} · ${formatMacroValue(charts.wti.latest.value ?? 0, charts.wti.unit)}`}
              subtitle={`As of ${formatMarketDate(charts.wti.latest.date)}`}
              series={[
                {
                  label: charts.wti.label,
                  color: colors.chart.negative,
                  points: charts.wti.points,
                },
              ]}
              prefix="$"
              showTrend={false}
            />
          </ChartGridItem>
        ) : null}
      </ResponsiveChartGrid>
    </View>
  );
}

function ResponsiveChartGrid({ columns, children }: { columns: 1 | 2; children: React.ReactNode }) {
  return (
    <View style={[workspaceStyles.chartGrid, columns === 2 && workspaceStyles.chartGridWide]}>
      {children}
    </View>
  );
}

function ChartGridItem({ columns, children }: { columns: 1 | 2; children: React.ReactNode }) {
  return (
    <View
      style={[workspaceStyles.chartGridItem, columns === 2 && workspaceStyles.chartGridItemWide]}
    >
      {children}
    </View>
  );
}

function TechnicalLineChart({
  title,
  subtitle,
  series,
  references = [],
  fixedDomain,
  prefix = "",
  suffix = "",
  showTrend = true,
  showValuesInLegend = false,
}: {
  title: string;
  subtitle: string;
  series: Array<{ label: string; color: string; points: SeriesPoint[] }>;
  references?: number[];
  fixedDomain?: [number, number];
  prefix?: string;
  suffix?: string;
  showTrend?: boolean;
  showValuesInLegend?: boolean;
}) {
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 122;
  const padding = 16;
  const allPoints = series.map((item) => item.points);
  const hasData = allPoints.some((points) => points.some((point) => point.value !== null));
  if (!hasData) {
    return (
      <ChartEmptyState
        title={title}
        message={`No labelled values are available for ${title.toLowerCase()} yet.`}
      />
    );
  }
  const { min, max } = chartScale(allPoints, references, fixedDomain);
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) =>
    padding + (1 - (value - min) / Math.max(max - min, 0.0001)) * plotHeight;
  return (
    <View style={styles.technicalChartCard}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={workspaceStyles.chartSubtitle}>{subtitle}</Text>
      {series.length > 1 ? (
        <View style={workspaceStyles.chartLegendRow}>
          {series.map((item) => {
            const latest = latestSeriesValue(item.points);
            return (
              <View key={`${item.label}-legend`} style={workspaceStyles.chartLegendItem}>
                <View style={[workspaceStyles.chartLegendDot, { backgroundColor: item.color }]} />
                <Text style={workspaceStyles.chartLegendText}>
                  {item.label}
                  {showValuesInLegend && latest !== null
                    ? ` ${prefix}${latest.toFixed(2)}${suffix}`
                    : ""}
                </Text>
              </View>
            );
          })}
        </View>
      ) : null}
      {showTrend ? (
        <View style={workspaceStyles.chartTrendRow}>
          {series.map((item) => (
            <Text key={`${item.label}-trend`} style={workspaceStyles.chartTrendText}>
              {compactTrend(series.length > 1 ? item.label : "", seriesTrend(item.points))}
            </Text>
          ))}
        </View>
      ) : null}
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          accessibilityRole="image"
          accessibilityLabel={`${title}. ${subtitle}. ${series.map((item) => `${describeLatest(item.label, item.points, prefix, suffix)} ${describeTrend(item.label, seriesTrend(item.points), prefix, suffix)}`).join(" ")}`}
        >
          {[0.25, 0.5, 0.75].map((position) => (
            <Line
              key={position}
              x1={padding}
              x2={width - padding}
              y1={padding + plotHeight * position}
              y2={padding + plotHeight * position}
              stroke={colors.chart.grid}
              strokeDasharray="3 4"
            />
          ))}
          {references.map((value) => (
            <Line
              key={value}
              x1={padding}
              x2={width - padding}
              y1={yForValue(value)}
              y2={yForValue(value)}
              stroke={colors.chart.reference}
              strokeDasharray="5 4"
            />
          ))}
          {series.map((item) => (
            <Path
              key={item.label}
              d={technicalPath(item.points, min, max, width, height, padding)}
              fill="none"
              stroke={item.color}
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          ))}
        </Svg>
      </View>
      <View style={styles.chartNumericAxis}>
        <Text style={styles.chartNumericText}>
          {prefix}
          {min.toFixed(1)}
          {suffix}
        </Text>
        <Text style={styles.chartNumericText}>
          {prefix}
          {max.toFixed(1)}
          {suffix}
        </Text>
      </View>
    </View>
  );
}

function MacdChart({
  macd,
  signal,
  histogram,
}: {
  macd: SeriesPoint[];
  signal: SeriesPoint[];
  histogram: SeriesPoint[];
}) {
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 128;
  const padding = 16;
  const hasData = [macd, signal, histogram].some((series) =>
    series.some((point) => point.value !== null),
  );
  if (!hasData)
    return <ChartEmptyState title="MACD" message="No labelled MACD values are available yet." />;
  const { min, max } = chartScale([macd, signal, histogram], [0]);
  const range = Math.max(max - min, 0.0001);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) => padding + (1 - (value - min) / range) * plotHeight;
  const baseline = yForValue(0);
  return (
    <View style={styles.technicalChartCard}>
      <Text style={styles.cardTitle}>MACD</Text>
      <Text style={workspaceStyles.chartSubtitle}>Signal and histogram</Text>
      <View style={workspaceStyles.chartLegendRow}>
        {[
          { label: "MACD", color: colors.chart.oscillator, points: macd },
          { label: "Signal", color: palette.signal, points: signal },
        ].map((item) => (
          <View key={item.label} style={workspaceStyles.chartLegendItem}>
            <View style={[workspaceStyles.chartLegendDot, { backgroundColor: item.color }]} />
            <Text style={workspaceStyles.chartLegendText}>
              {item.label} {latestSeriesValue(item.points)?.toFixed(2) ?? "—"}
            </Text>
          </View>
        ))}
      </View>
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          accessibilityRole="image"
          accessibilityLabel={`MACD and signal line chart with a positive or negative histogram. ${describeLatest("MACD", macd)} ${describeLatest("Signal", signal)}`}
        >
          <Line
            x1={padding}
            x2={width - padding}
            y1={baseline}
            y2={baseline}
            stroke={colors.chart.reference}
            strokeDasharray="5 4"
          />
          {histogram.map((point, index) => {
            if (point.value === null) return null;
            const x = padding + (index / Math.max(histogram.length - 1, 1)) * plotWidth;
            const y = yForValue(point.value);
            return (
              <Rect
                key={point.date}
                x={x - 1.5}
                y={Math.min(y, baseline)}
                width={3}
                height={Math.abs(y - baseline)}
                fill={point.value >= 0 ? colors.chart.positive : colors.chart.negative}
              />
            );
          })}
          <Path
            d={technicalPath(macd, min, max, width, height, padding)}
            fill="none"
            stroke={colors.chart.oscillator}
            strokeWidth="2.3"
          />
          <Path
            d={technicalPath(signal, min, max, width, height, padding)}
            fill="none"
            stroke={palette.signal}
            strokeWidth="2.3"
          />
        </Svg>
      </View>
      <View style={styles.chartNumericAxis}>
        <Text style={styles.chartNumericText}>{min.toFixed(2)}</Text>
        <Text style={styles.chartNumericText}>{max.toFixed(2)}</Text>
      </View>
    </View>
  );
}

function TechnicalBarChart({
  title,
  subtitle,
  points,
  color,
}: {
  title: string;
  subtitle: string;
  points: SeriesPoint[];
  color: string;
}) {
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 104;
  const padding = 16;
  const values = points.flatMap((point) => (point.value === null ? [] : [point.value]));
  if (!values.length)
    return (
      <ChartEmptyState
        title={title}
        message={`No labelled values are available for ${title.toLowerCase()} yet.`}
      />
    );
  const max = Math.max(...values);
  const scaleMax = chartBarScaleMaximum(values);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  return (
    <View style={styles.technicalChartCard}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={workspaceStyles.chartSubtitle}>{subtitle}</Text>
      <Text style={workspaceStyles.chartTrendText}>
        Latest {((latestSeriesValue(points) ?? 0) / 1_000_000).toFixed(1)}M · Peak{" "}
        {(max / 1_000_000).toFixed(1)}M
      </Text>
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          accessibilityRole="image"
          accessibilityLabel={`${title}. ${subtitle}. ${describeLatest(title, points, "", "", (value) => `${(value / 1_000_000).toFixed(1)}M shares`)} ${describeTrend(title, seriesTrend(points))}`}
        >
          {points.map((point, index) => {
            if (point.value === null) return null;
            const barWidth = Math.max(1.5, plotWidth / points.length - 1);
            const x = padding + (index / points.length) * plotWidth;
            const barHeight = (point.value / scaleMax) * plotHeight;
            return (
              <Rect
                key={point.date}
                x={x}
                y={height - padding - barHeight}
                width={barWidth}
                height={barHeight}
                fill={color}
                opacity={0.78}
              />
            );
          })}
        </Svg>
      </View>
    </View>
  );
}

function ChartEmptyState({ title, message }: { title: string; message: string }) {
  return (
    <View accessibilityLiveRegion="polite" style={[styles.technicalChartCard, styles.chartNoData]}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.mutedText}>{message}</Text>
    </View>
  );
}
