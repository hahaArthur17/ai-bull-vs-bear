import { useMemo, useState } from "react";
import { PanResponder, Pressable, ScrollView, Text, View } from "react-native";
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop } from "react-native-svg";

import { BackButton, FailureView, LoadingView, Metric, SectionHeader } from "../components/common";
import { formatChartDate, formatMarketDate, formatQuoteTime } from "../dateFormat";
import {
  calculateRsi,
  calculateVolatility,
  chartScale,
  exponentialMovingAverage,
  formatMacroValue,
  macroChart,
  simpleMovingAverage,
  technicalPath,
} from "../research/chartMath";
import type { MacroChart, SeriesPoint } from "../research/chartMath";
import { appStyles as styles, palette } from "../theme";
import type { Stock, StockBundle } from "../types";

export function StockDetailScreen({
  stock,
  bundle,
  loading,
  error,
  onBack,
  onRetry,
  onEvidence,
  onDebate,
  isWatched,
  onToggleWatchlist,
}: {
  stock: Stock | null;
  bundle: StockBundle | null;
  loading: boolean;
  error: string;
  onBack: () => void;
  onRetry: () => void;
  onEvidence: () => void;
  onDebate: () => void;
  isWatched: boolean;
  onToggleWatchlist: () => void;
}) {
  if (loading) return <LoadingView label="Loading stock detail..." onBack={onBack} />;
  if (stock?.coverage_status === "catalog_only") {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <BackButton onPress={onBack} />
        <View style={styles.detailHeader}>
          <View>
            <Text style={styles.eyebrow}>{stock.exchange} · CATALOG ONLY</Text>
            <Text style={styles.detailTitle}>{stock.company_name}</Text>
            <Text style={styles.detailTicker}>
              {stock.ticker} · {stock.sector || "Classification unavailable"}
            </Text>
          </View>
          <Pressable
            accessibilityLabel={isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
            accessibilityRole="button"
            accessibilityState={{ selected: isWatched }}
            onPress={onToggleWatchlist}
          >
            <Text style={[styles.star, isWatched && styles.starActive]}>
              {isWatched ? "★" : "☆"}
            </Text>
          </Pressable>
        </View>
        <View style={styles.aboutCard}>
          <Text style={styles.cardTitle}>Identity available, analysis not configured</Text>
          <Text style={styles.mutedText}>
            This symbol comes from the versioned SEC catalog and can be saved to your Watchlist.
            Cached prices, evidence, technical signals, and Bull vs Bear are not available for it.
          </Text>
        </View>
        <View style={styles.aboutCard}>
          <Text style={styles.cardTitle}>Zero provider calls</Text>
          <Text style={styles.mutedText}>
            Opening this profile did not request market data, news, or an AI model.
          </Text>
          {stock.sec_cik ? <Text style={styles.mutedText}>SEC CIK {stock.sec_cik}</Text> : null}
        </View>
        <Pressable
          accessibilityLabel={isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
          accessibilityRole="button"
          accessibilityState={{ selected: isWatched }}
          style={styles.secondaryButton}
          onPress={onToggleWatchlist}
        >
          <Text style={styles.secondaryButtonText}>
            {isWatched ? "Remove from Watchlist" : "Add to Watchlist"}
          </Text>
        </Pressable>
      </ScrollView>
    );
  }
  if (!bundle) {
    return (
      <FailureView
        message={error || "Stock details are unavailable."}
        onBack={onBack}
        onRetry={onRetry}
      />
    );
  }
  const latest = bundle.prices[bundle.prices.length - 1];
  const hasVerifiedMarketData = latest.source === "daily_market_cache";
  const quote = bundle.quote;
  const hasLatestQuote = quote !== null;
  const priceSource = quote ? "LATEST MARKET QUOTE" : latest.source === "daily_market_cache" ? "DAILY MARKET CACHE" : "DEMO FALLBACK";
  const priceStatus = latest.is_stale ? " · STALE" : "";
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <View style={styles.detailHeader}>
        <View>
          <Text style={styles.eyebrow}>{bundle.stock.exchange} · {priceSource}{priceStatus}</Text>
          <Text style={styles.detailTitle}>{bundle.stock.company_name}</Text>
          <Text style={styles.detailTicker}>
            {bundle.stock.ticker} · {bundle.stock.sector || "Classification unavailable"}
          </Text>
        </View>
        <Pressable
          accessibilityLabel={isWatched ? `Remove ${bundle.stock.ticker} from watchlist` : `Add ${bundle.stock.ticker} to watchlist`}
          accessibilityRole="button"
          accessibilityState={{ selected: isWatched }}
          onPress={onToggleWatchlist}
        ><Text style={[styles.star, isWatched && styles.starActive]}>{isWatched ? "★" : "☆"}</Text></Pressable>
      </View>
      <View style={styles.priceCard}>
        <Text style={styles.cardLabel}>{quote ? "LATEST QUOTE" : hasVerifiedMarketData ? "LATEST DAILY CLOSE" : "VERIFIED PRICE UNAVAILABLE"}</Text>
        {hasLatestQuote || hasVerifiedMarketData ? (
          <Text style={styles.priceValue}>{"$"}{(bundle.quote?.close ?? latest.close).toFixed(2)}</Text>
        ) : (
          <Text style={styles.unavailablePrice}>—</Text>
        )}
        <Text accessibilityLiveRegion="polite" style={styles.priceMeta}>
          {quote
            ? `Quote timestamp ${formatQuoteTime(quote.as_of)}`
            : hasVerifiedMarketData
              ? `Market close on ${formatMarketDate(latest.date)}`
              : "The earlier $207.40 was generated demo data, not an Apple market close."}
        </Text>
        <Text style={styles.priceMeta}>
          {quote
            ? `Latest quote is cached on the server for one minute${hasVerifiedMarketData ? "; the curve below uses daily closes." : "."}`
            : hasVerifiedMarketData
              ? `Verified daily OHLCV cache${latest.is_stale ? "; refresh needed." : "."}`
              : "A verified daily price will appear after the AAPL cache refresh completes."}
        </Text>
        {hasVerifiedMarketData ? (
          <InteractivePriceChart dailyPrices={bundle.prices} weeklyPrices={bundle.weekly_history} />
        ) : (
          <View style={styles.chartUnavailable}>
            <Text style={styles.chartUnavailableText}>No curve is shown until market data is verified.</Text>
          </View>
        )}
      </View>
      {hasVerifiedMarketData ? (
        <>
          <MacroContextPanel context={bundle.macro_context} />
          <SectionHeader title="Signal snapshot" meta="technical agent" />
          <View style={styles.metricGrid}>
            <Metric label="RSI" value={bundle.indicators.rsi.toFixed(1)} />
            <Metric label="MACD" value={bundle.indicators.macd.toFixed(2)} />
            <Metric label="MA20" value={bundle.indicators.moving_average_20.toFixed(2)} />
            <Metric label="Volatility" value={bundle.indicators.volatility.toFixed(1) + "%"} />
          </View>
          <TechnicalPanels prices={bundle.prices} />
          <View style={styles.signalCard}><Text style={styles.signalText}>{bundle.indicators.signal_summary}</Text></View>
        </>
      ) : (
        <View style={styles.signalUnavailable}>
          <Text style={styles.signalUnavailableTitle}>Technical signals are paused</Text>
          <Text style={styles.signalUnavailableText}>RSI, MACD, and the curve will appear once the AAPL daily-price cache has verified history.</Text>
        </View>
      )}
      <View style={styles.actionRow}>
        <Pressable accessibilityHint="Opens the dated evidence used by the research workflow." accessibilityRole="button" style={styles.secondaryButton} onPress={onEvidence}><Text style={styles.secondaryButtonText}>Evidence board</Text></Pressable>
        <Pressable accessibilityHint="Starts Bull vs Bear for this research-ready security." accessibilityRole="button" style={styles.primaryButton} onPress={onDebate}><Text style={styles.primaryButtonText}>Start Bull vs Bear →</Text></Pressable>
      </View>
    </ScrollView>
  );
}

type ChartRange = "1M" | "3M" | "6M" | "1Y";

type InteractivePricePoint = {
  date: string;
  close: number;
  frequency: "daily" | "weekly";
  source: "daily_market_cache" | "demo_fallback" | "alpha_vantage_weekly";
  ma20: number | null;
  ma50: number | null;
  is_stale?: boolean;
  retrieved_at?: string;
};

function InteractivePriceChart({
  dailyPrices,
  weeklyPrices,
}: {
  dailyPrices: StockBundle["prices"];
  weeklyPrices: StockBundle["weekly_history"];
}) {
  const [range, setRange] = useState<ChartRange>("1M");
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [chartWidth, setChartWidth] = useState(320);
  const points: InteractivePricePoint[] = useMemo(() => {
    const source = range === "1M" || range === "3M"
      ? dailyPrices.map((point) => ({ ...point, frequency: "daily" as const }))
      : weeklyPrices;
    const visibleLimit = range === "1M" ? 22 : range === "3M" ? 66 : range === "6M" ? 27 : 53;
    const ma20 = simpleMovingAverage(source.map((point) => point.close), 20);
    const ma50 = simpleMovingAverage(source.map((point) => point.close), 50);
    const firstVisibleIndex = Math.max(0, source.length - visibleLimit);
    return source.slice(firstVisibleIndex).map((point, visibleIndex) => {
      const sourceIndex = firstVisibleIndex + visibleIndex;
      return { ...point, ma20: ma20[sourceIndex], ma50: ma50[sourceIndex] };
    });
  }, [dailyPrices, range, weeklyPrices]);
  const width = 320;
  const height = 154;
  const padding = { top: 14, right: 12, bottom: 26, left: 12 };
  if (points.length < 2) {
    return (
      <View style={styles.lineChart}>
        <View style={styles.chartHeader}>
          <Text style={styles.chartLabel}>PRICE HISTORY</Text>
          <Text style={styles.chartRange}>{range}</Text>
        </View>
        <View style={styles.rangeSelector}>
          {(["1M", "3M", "6M", "1Y"] as ChartRange[]).map((option) => (
            <Pressable
              key={option}
              style={[styles.rangeButton, option === range && styles.rangeButtonActive]}
              onPress={() => { setRange(option); setSelectedIndex(-1); }}
            >
              <Text style={[styles.rangeButtonText, option === range && styles.rangeButtonTextActive]}>{option}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.chartUnavailableText}>No labelled {range === "1M" || range === "3M" ? "daily" : "weekly"} history is available yet.</Text>
      </View>
    );
  }
  const plottedValues = points.flatMap((point) => [point.close, point.ma20, point.ma50].filter((value): value is number => value !== null));
  const minClose = Math.min(...plottedValues);
  const maxClose = Math.max(...plottedValues);
  const closeRange = Math.max(0.01, maxClose - minClose);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const coordinates = points.map((point, index) => {
    const x = padding.left + (index / Math.max(1, points.length - 1)) * plotWidth;
    const y = padding.top + (1 - (point.close - minClose) / closeRange) * plotHeight;
    return { x, y };
  });
  const linePath = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
  const averagePath = (key: "ma20" | "ma50") => {
    let started = false;
    return points.map((point, index) => {
      const value = point[key];
      if (value === null) {
        started = false;
        return "";
      }
      const x = padding.left + (index / Math.max(1, points.length - 1)) * plotWidth;
      const y = padding.top + (1 - (value - minClose) / closeRange) * plotHeight;
      const command = started ? "L" : "M";
      started = true;
      return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(" ");
  };
  const ma20Path = averagePath("ma20");
  const ma50Path = averagePath("ma50");
  const first = coordinates[0];
  const last = coordinates[coordinates.length - 1];
  const areaPath = `${linePath} L${last.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} L${first.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} Z`;
  const activeIndex = Math.min(Math.max(selectedIndex < 0 ? points.length - 1 : selectedIndex, 0), points.length - 1);
  const activePoint = points[activeIndex];
  const activeCoordinate = coordinates[activeIndex];
  const movingAverageUnit = activePoint.frequency === "daily" ? "d" : "w";
  const setPointFromLocation = (locationX: number) => {
    const svgX = (locationX / Math.max(chartWidth, 1)) * width;
    const ratio = Math.min(1, Math.max(0, (svgX - padding.left) / plotWidth));
    setSelectedIndex(Math.round(ratio * (points.length - 1)));
  };
  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: () => true,
    onStartShouldSetPanResponder: () => true,
    onPanResponderGrant: (event) => setPointFromLocation(event.nativeEvent.locationX),
    onPanResponderMove: (event) => setPointFromLocation(event.nativeEvent.locationX),
  });
  const frequencyLabel = activePoint.frequency === "daily"
    ? activePoint.is_stale
      ? "Daily market cache · stale"
      : "Daily market cache · verified"
    : activePoint.retrieved_at
      ? `Weekly Alpha Vantage history · refreshed ${formatQuoteTime(activePoint.retrieved_at)}`
      : "Weekly Alpha Vantage history";

  return (
    <View
      style={styles.lineChart}
      accessibilityLabel={`AAPL ${range} price chart. Selected ${activePoint.frequency} close: ${formatMarketDate(activePoint.date)}, $${activePoint.close.toFixed(2)}. Drag across the chart or use Earlier and Later buttons to inspect points.`}
    >
      <View style={styles.chartHeader}>
        <Text style={styles.chartLabel}>{activePoint.frequency.toUpperCase()} PRICE · {range}</Text>
        <Text style={styles.chartRange}>{formatChartDate(points[0].date)} – {formatChartDate(points[points.length - 1].date)}</Text>
      </View>
      <View style={styles.priceChartLegend}>
        <Text style={styles.priceLegendClose}>● Close</Text>
        <Text style={styles.priceLegendMa20}>● MA20{movingAverageUnit}</Text>
        <Text style={styles.priceLegendMa50}>● MA50{movingAverageUnit}</Text>
      </View>
      <View style={styles.rangeSelector}>
        {(["1M", "3M", "6M", "1Y"] as ChartRange[]).map((option) => (
          <Pressable
            key={option}
            accessibilityRole="button"
            accessibilityState={{ selected: option === range }}
            style={[styles.rangeButton, option === range && styles.rangeButtonActive]}
            onPress={() => { setRange(option); setSelectedIndex(-1); }}
          >
            <Text style={[styles.rangeButtonText, option === range && styles.rangeButtonTextActive]}>{option}</Text>
          </Pressable>
        ))}
      </View>
      <View
        style={styles.chartTouchArea}
        onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}
        {...panResponder.panHandlers}
      >
        <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image">
          <Defs>
            <LinearGradient id="price-area" x1="0" x2="0" y1="0" y2="1">
              <Stop offset="0" stopColor="#9bc6ac" stopOpacity="0.46" />
              <Stop offset="1" stopColor="#9bc6ac" stopOpacity="0" />
            </LinearGradient>
          </Defs>
          {[0.25, 0.5, 0.75].map((position) => (
            <Line
              key={position}
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + plotHeight * position}
              y2={padding.top + plotHeight * position}
              stroke="#ffffff"
              strokeOpacity="0.16"
              strokeDasharray="4 4"
            />
          ))}
          <Path d={areaPath} fill="url(#price-area)" />
          <Path d={linePath} fill="none" stroke="#d7f0dc" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <Path d={ma20Path} fill="none" stroke="#f5c86e" strokeWidth="2" strokeLinecap="round" />
          <Path d={ma50Path} fill="none" stroke="#d59be3" strokeWidth="2" strokeLinecap="round" strokeDasharray="5 3" />
          <Line x1={activeCoordinate.x} x2={activeCoordinate.x} y1={padding.top} y2={height - padding.bottom} stroke="#fffdf8" strokeOpacity="0.7" strokeDasharray="3 3" />
          <Circle cx={activeCoordinate.x} cy={activeCoordinate.y} r="5" fill="#fffdf8" />
          <Circle cx={activeCoordinate.x} cy={activeCoordinate.y} r="2.5" fill="#d95c3b" />
        </Svg>
      </View>
      <View style={styles.chartAxis}>
        <Text style={styles.chartAxisText}>${minClose.toFixed(2)}</Text>
        <Text style={styles.chartAxisText}>${maxClose.toFixed(2)}</Text>
      </View>
      <View style={styles.chartTooltip}>
        <Text style={styles.chartTooltipPrice}>${activePoint.close.toFixed(2)}</Text>
        <Text style={styles.chartTooltipMeta}>{formatMarketDate(activePoint.date)} · {frequencyLabel}</Text>
        <Text style={styles.chartTooltipMeta}>
          MA20{movingAverageUnit} {activePoint.ma20 === null ? "not enough history" : `$${activePoint.ma20.toFixed(2)}`}
          {" · "}
          MA50{movingAverageUnit} {activePoint.ma50 === null ? "not enough history" : `$${activePoint.ma50.toFixed(2)}`}
        </Text>
      </View>
      <View style={styles.chartInspector}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Inspect earlier price point"
          disabled={activeIndex === 0}
          style={[styles.chartStepButton, activeIndex === 0 && styles.chartStepDisabled]}
          onPress={() => setSelectedIndex(activeIndex - 1)}
        >
          <Text style={styles.chartStepText}>← Earlier</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Inspect later price point"
          disabled={activeIndex === points.length - 1}
          style={[styles.chartStepButton, activeIndex === points.length - 1 && styles.chartStepDisabled]}
          onPress={() => setSelectedIndex(activeIndex + 1)}
        >
          <Text style={styles.chartStepText}>Later →</Text>
        </Pressable>
      </View>
    </View>
  );
}

function TechnicalPanels({ prices }: { prices: StockBundle["prices"] }) {
  const data = useMemo(() => {
    const closes = prices.map((point) => point.close);
    const toPoints = (values: Array<number | null>): SeriesPoint[] => values.map((value, index) => ({ date: prices[index].date, value }));
    const ema12 = exponentialMovingAverage(closes, 12);
    const ema26 = exponentialMovingAverage(closes, 26);
    const macd = closes.map((_, index) => ema12[index] - ema26[index]);
    const signal = exponentialMovingAverage(macd, 9);
    return {
      ma20: toPoints(simpleMovingAverage(closes, 20)),
      ma50: toPoints(simpleMovingAverage(closes, 50)),
      rsi: toPoints(calculateRsi(closes)),
      macd: toPoints(macd),
      macdSignal: toPoints(signal),
      histogram: toPoints(macd.map((value, index) => value - signal[index])),
      volume: prices.map((point) => ({ date: point.date, value: point.volume })),
      volatility: toPoints(calculateVolatility(closes)),
    };
  }, [prices]);
  const latestDate = prices[prices.length - 1]?.date;
  return (
    <View style={styles.technicalPanels}>
      <SectionHeader
        title="Continuous technical panels"
        meta={latestDate ? `as of ${formatMarketDate(latestDate)}` : "verified daily cache"}
      />
      <TechnicalLineChart
        title="Moving averages"
        subtitle="MA20 / MA50 · daily closes"
        series={[
          { label: "MA20", color: palette.bull, points: data.ma20 },
          { label: "MA50", color: palette.signal, points: data.ma50 },
        ]}
      />
      <TechnicalLineChart
        title="Relative strength"
        subtitle="RSI 14 · 30 / 70 reference lines"
        series={[{ label: "RSI", color: "#7664a8", points: data.rsi }]}
        references={[30, 70]}
        fixedDomain={[0, 100]}
      />
      <MacdChart macd={data.macd} signal={data.macdSignal} histogram={data.histogram} />
      <TechnicalBarChart title="Daily volume" subtitle="Shares traded" points={data.volume} color="#638ba2" />
      <TechnicalLineChart
        title="Annualised volatility"
        subtitle="20-session realised volatility"
        series={[{ label: "Volatility", color: palette.bear, points: data.volatility }]}
        suffix="%"
      />
    </View>
  );
}

function MacroContextPanel({ context }: { context: StockBundle["macro_context"] }) {
  const charts = useMemo(() => ({
    sp500: macroChart(context, "sp500", "S&P 500"),
    vix: macroChart(context, "vix", "VIX"),
    effectiveRate: macroChart(context, "effective_fed_funds_rate", "Effective rate"),
    twoYear: macroChart(context, "treasury_2y_yield", "2Y"),
    tenYear: macroChart(context, "treasury_10y_yield", "10Y"),
    thirtyYear: macroChart(context, "treasury_30y_yield", "30Y"),
    wti: macroChart(context, "wti_spot", "WTI crude"),
  }), [context]);
  if (!Object.values(charts).some(Boolean)) return null;
  const rateSeries = [charts.effectiveRate, charts.twoYear, charts.tenYear, charts.thirtyYear]
    .filter((chart): chart is MacroChart => chart !== null);
  const rateLatest = rateSeries
    .map((chart) => `${chart.label} ${formatMacroValue(chart.latest.value ?? 0, chart.unit)} (${formatChartDate(chart.latest.date)})`)
    .join(" · ");

  return (
    <View style={styles.macroSection}>
      <SectionHeader title="Market backdrop" meta="cached daily context" />
      <View style={styles.macroDisclosure}>
        <Text style={styles.macroDisclosureTitle}>Background, not a price-move explanation</Text>
        <Text style={styles.macroDisclosureText}>These dated market series can frame broad conditions. They do not prove why AAPL moved on a particular day and are not personal investment advice.</Text>
      </View>
      {charts.sp500 ? (
        <TechnicalLineChart
          title={`${charts.sp500.label} · ${formatMacroValue(charts.sp500.latest.value ?? 0, charts.sp500.unit)}`}
          subtitle={`${charts.sp500.source.toUpperCase()} · latest ${formatMarketDate(charts.sp500.latest.date)} · last 30 observations`}
          series={[{ label: charts.sp500.label, color: "#3e8b6d", points: charts.sp500.points }]}
        />
      ) : null}
      {charts.vix ? (
        <TechnicalLineChart
          title={`${charts.vix.label} · ${formatMacroValue(charts.vix.latest.value ?? 0, charts.vix.unit)}`}
          subtitle={`${charts.vix.source.toUpperCase()} · latest ${formatMarketDate(charts.vix.latest.date)} · last 30 observations`}
          series={[{ label: charts.vix.label, color: "#7664a8", points: charts.vix.points }]}
        />
      ) : null}
      {rateSeries.length ? (
        <TechnicalLineChart
          title="U.S. rates"
          subtitle={rateLatest}
          series={rateSeries.map((chart, index) => ({
            label: chart.label,
            color: ["#d95c3b", "#638ba2", "#3e8b6d", "#7664a8"][index],
            points: chart.points,
          }))}
          suffix="%"
        />
      ) : null}
      {charts.wti ? (
        <TechnicalLineChart
          title={`${charts.wti.label} · ${formatMacroValue(charts.wti.latest.value ?? 0, charts.wti.unit)}`}
          subtitle={`${charts.wti.source.toUpperCase()} · latest ${formatMarketDate(charts.wti.latest.date)} · last 30 observations`}
          series={[{ label: charts.wti.label, color: "#b95455", points: charts.wti.points }]}
          prefix="$"
        />
      ) : null}
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
}: {
  title: string;
  subtitle: string;
  series: Array<{ label: string; color: string; points: SeriesPoint[] }>;
  references?: number[];
  fixedDomain?: [number, number];
  prefix?: string;
  suffix?: string;
}) {
  const width = 320;
  const height = 122;
  const padding = 16;
  const allPoints = series.map((item) => item.points);
  const hasData = allPoints.some((points) => points.some((point) => point.value !== null));
  if (!hasData) return null;
  const { min, max } = chartScale(allPoints, references, fixedDomain);
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) => padding + (1 - (value - min) / Math.max(max - min, 0.0001)) * plotHeight;
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}>
        <View><Text style={styles.cardTitle}>{title}</Text><Text style={styles.mutedText}>{subtitle}</Text></View>
        <Text style={styles.chartLegend}>{series.map((item) => item.label).join(" · ")}</Text>
      </View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel={`${title}. ${subtitle}.`}>
        {[0.25, 0.5, 0.75].map((position) => <Line key={position} x1={padding} x2={width - padding} y1={padding + plotHeight * position} y2={padding + plotHeight * position} stroke="#d8d5ca" strokeDasharray="3 4" />)}
        {references.map((value) => <Line key={value} x1={padding} x2={width - padding} y1={yForValue(value)} y2={yForValue(value)} stroke="#b4a67d" strokeDasharray="5 4" />)}
        {series.map((item) => <Path key={item.label} d={technicalPath(item.points, min, max, width, height, padding)} fill="none" stroke={item.color} strokeWidth="2.5" strokeLinecap="round" />)}
      </Svg>
      <View style={styles.chartNumericAxis}><Text style={styles.chartNumericText}>{prefix}{min.toFixed(1)}{suffix}</Text><Text style={styles.chartNumericText}>{prefix}{max.toFixed(1)}{suffix}</Text></View>
    </View>
  );
}

function MacdChart({ macd, signal, histogram }: { macd: SeriesPoint[]; signal: SeriesPoint[]; histogram: SeriesPoint[] }) {
  const width = 320;
  const height = 128;
  const padding = 16;
  const { min, max } = chartScale([macd, signal, histogram], [0]);
  const range = Math.max(max - min, 0.0001);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) => padding + (1 - (value - min) / range) * plotHeight;
  const baseline = yForValue(0);
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>MACD</Text><Text style={styles.mutedText}>MACD / signal lines · histogram</Text></View><Text style={styles.chartLegend}>MACD · Signal</Text></View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel="MACD and signal line chart with a positive or negative histogram.">
        <Line x1={padding} x2={width - padding} y1={baseline} y2={baseline} stroke="#b4a67d" strokeDasharray="5 4" />
        {histogram.map((point, index) => {
          if (point.value === null) return null;
          const x = padding + (index / Math.max(histogram.length - 1, 1)) * plotWidth;
          const y = yForValue(point.value);
          return <Rect key={point.date} x={x - 1.5} y={Math.min(y, baseline)} width={3} height={Math.abs(y - baseline)} fill={point.value >= 0 ? "#92bd9d" : "#df9c99"} />;
        })}
        <Path d={technicalPath(macd, min, max, width, height, padding)} fill="none" stroke="#7664a8" strokeWidth="2.3" />
        <Path d={technicalPath(signal, min, max, width, height, padding)} fill="none" stroke={palette.signal} strokeWidth="2.3" />
      </Svg>
      <View style={styles.chartNumericAxis}><Text style={styles.chartNumericText}>{min.toFixed(2)}</Text><Text style={styles.chartNumericText}>{max.toFixed(2)}</Text></View>
    </View>
  );
}

function TechnicalBarChart({ title, subtitle, points, color }: { title: string; subtitle: string; points: SeriesPoint[]; color: string }) {
  const width = 320;
  const height = 104;
  const padding = 16;
  const values = points.flatMap((point) => point.value === null ? [] : [point.value]);
  if (!values.length) return null;
  const max = Math.max(...values);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>{title}</Text><Text style={styles.mutedText}>{subtitle}</Text></View><Text style={styles.chartLegend}>max {(max / 1_000_000).toFixed(1)}M</Text></View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel={`${title}. ${subtitle}.`}>
        {points.map((point, index) => {
          if (point.value === null) return null;
          const barWidth = Math.max(1.5, plotWidth / points.length - 1);
          const x = padding + (index / points.length) * plotWidth;
          const barHeight = (point.value / max) * plotHeight;
          return <Rect key={point.date} x={x} y={height - padding - barHeight} width={barWidth} height={barHeight} fill={color} opacity={0.78} />;
        })}
      </Svg>
    </View>
  );
}
