import { useMemo, useState } from "react";
import { PanResponder, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop } from "react-native-svg";

import { BackButton, FailureView, FocusablePressable, LoadingView, Metric, SectionHeader } from "../components/common";
import { formatChartDate, formatMarketDate, formatQuoteTime } from "../dateFormat";
import {
  calculateRsi,
  calculateVolatility,
  calculateMacd,
  chartBarScaleMaximum,
  chartScale,
  formatMacroValue,
  macroChart,
  seriesTrend,
  simpleMovingAverage,
  technicalPath,
} from "../research/chartMath";
import type { MacroChart, SeriesPoint } from "../research/chartMath";
import { getResearchWorkspaceLayout } from "../research/workspaceLayout";
import { getQuoteProvenance } from "../stockResearchSummary";
import type { QuoteProvenance } from "../stockResearchSummary";
import { appStyles as styles, colors, palette, radii, spacing } from "../theme";
import type { Stock, StockBundle, TechnicalIndicators } from "../types";

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
  const { width: viewportWidth } = useWindowDimensions();
  if (loading) return <LoadingView label="Loading stock detail..." onBack={onBack} />;
  if (stock?.coverage_status === "catalog_only") {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <BackButton onPress={onBack} />
        <StockResearchHeader stock={stock} isWatched={isWatched} onToggleWatchlist={onToggleWatchlist} />
        <View style={styles.catalogIdentityCard}>
          <Text style={styles.cardLabel}>CATALOG IDENTITY</Text>
          <Text style={styles.catalogAvailability}>Watchlist available · research unavailable</Text>
          <Text style={styles.mutedText}>
            This identity comes from the versioned SEC catalog. It can be saved to your Watchlist,
            but cached prices, evidence, technical signals, and Bull vs Bear are not configured.
          </Text>
          <Text style={styles.catalogMetadata}>Source · Versioned SEC security catalog</Text>
          <Text style={styles.catalogMetadata}>Coverage checked · {formatQuoteTime(stock.coverage_updated_at)}</Text>
          {stock.sec_cik ? <Text style={styles.catalogMetadata}>SEC CIK · {stock.sec_cik}</Text> : null}
        </View>
        <View style={styles.catalogBoundaryCard}>
          <Text style={styles.cardTitle}>Identity-only boundary</Text>
          <Text style={styles.mutedText}>
            Opening this profile did not request market data, news, evidence retrieval, or an AI model.
          </Text>
        </View>
        <FocusablePressable
          accessibilityLabel={isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
          accessibilityRole="button"
          accessibilityState={{ selected: isWatched }}
          style={styles.secondaryButton}
          onPress={onToggleWatchlist}
        >
          <Text style={styles.secondaryButtonText}>
            {isWatched ? "Remove from Watchlist" : "Add to Watchlist"}
          </Text>
        </FocusablePressable>
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
  const quoteProvenance = getQuoteProvenance(bundle);
  const {
    curveSource,
    hasPriceCurve,
    hasVerifiedMarketData,
    preferredChartRange,
  } = quoteProvenance;
  const availability = bundle.indicators.availability;
  const hasAnyTechnicalData = Boolean(availability && Object.values(availability).some(Boolean));
  const historyExplanation = bundle.indicators.history?.explanation
    ?? "Daily history has not been assessed.";
  const workspaceLayout = getResearchWorkspaceLayout(viewportWidth);
  const isSimulated = bundle.data_mode === "review_fixture"
    || bundle.indicators.history?.provenance === "review_fixture";
  const snapshot = (
    <SignalSnapshot
      availability={availability}
      indicators={bundle.indicators}
      hasAnyTechnicalData={hasAnyTechnicalData}
      historyExplanation={historyExplanation}
      hasVerifiedMarketData={hasVerifiedMarketData}
      isSimulated={isSimulated}
    />
  );
  const actions = <ResearchActions onDebate={onDebate} onEvidence={onEvidence} />;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <StockResearchHeader stock={bundle.stock} isWatched={isWatched} onToggleWatchlist={onToggleWatchlist} />
      <View style={[workspaceStyles.overview, workspaceLayout.overviewColumns === 2 && workspaceStyles.overviewDesktop]}>
        <View style={workspaceStyles.primaryColumn}>
          <PriceResearchCard
            ticker={bundle.stock.ticker}
            quoteProvenance={quoteProvenance}
            curveSource={curveSource}
            hasPriceCurve={hasPriceCurve}
            dailyPrices={bundle.prices}
            weeklyPrices={bundle.weekly_history}
            initialRange={preferredChartRange}
            historyExplanation={historyExplanation}
          />
          {!workspaceLayout.showReadinessSidebar ? snapshot : null}
          <TechnicalPanels prices={bundle.prices} availability={availability} chartColumns={workspaceLayout.chartColumns} />
          <MacroContextPanel context={bundle.macro_context} chartColumns={workspaceLayout.chartColumns} />
        </View>
        {workspaceLayout.showReadinessSidebar ? (
          <View style={workspaceStyles.readinessSidebar}>
            {snapshot}
            {actions}
          </View>
        ) : null}
      </View>
      {!workspaceLayout.showReadinessSidebar ? actions : null}
    </ScrollView>
  );
}

function StockResearchHeader({
  stock,
  isWatched,
  onToggleWatchlist,
}: {
  stock: Stock;
  isWatched: boolean;
  onToggleWatchlist: () => void;
}) {
  const isCatalogOnly = stock.coverage_status === "catalog_only";
  const coverageLabel = isCatalogOnly ? "Watchlist only" : "Research coverage available";
  return (
    <View style={styles.researchHeader}>
      <View style={styles.tickerTile}><Text style={styles.tickerTileText}>{stock.ticker.slice(0, 1)}</Text></View>
      <View style={styles.researchHeaderCopy}>
        <Text style={styles.eyebrow}>{stock.exchange} · {isCatalogOnly ? "CATALOG IDENTITY" : "STOCK RESEARCH"}</Text>
        <Text style={styles.detailTitle}>{stock.company_name}</Text>
        <Text style={styles.detailTicker}>{stock.ticker} · {stock.sector || "Classification unavailable"}</Text>
        <Text style={[styles.coverageStatus, isCatalogOnly && styles.coverageStatusCatalog]}>{coverageLabel}</Text>
      </View>
      <FocusablePressable
        accessibilityLabel={isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
        accessibilityRole="button"
        accessibilityState={{ selected: isWatched }}
        onPress={onToggleWatchlist}
        style={styles.researchWatchButton}
      >
        <Text style={[styles.star, isWatched && styles.starActive]}>{isWatched ? "★" : "☆"}</Text>
      </FocusablePressable>
    </View>
  );
}

function PriceResearchCard({
  ticker,
  quoteProvenance,
  curveSource,
  hasPriceCurve,
  dailyPrices,
  weeklyPrices,
  initialRange,
  historyExplanation,
}: {
  ticker: string;
  quoteProvenance: QuoteProvenance;
  curveSource: string;
  hasPriceCurve: boolean;
  dailyPrices: StockBundle["prices"];
  weeklyPrices: StockBundle["weekly_history"];
  initialRange: ChartRange;
  historyExplanation: string;
}) {
  return (
    <View style={styles.priceCard}>
      <View style={styles.priceSummaryHeader}>
        <Text style={styles.cardLabel}>{quoteProvenance.label.toUpperCase()}</Text>
        <Text style={styles.priceFreshness}>{quoteProvenance.freshness}</Text>
      </View>
      {quoteProvenance.value !== null ? (
        <Text accessibilityLiveRegion="polite" style={styles.priceValue}>{"$"}{quoteProvenance.value.toFixed(2)}</Text>
      ) : (
        <Text style={styles.unavailablePrice}>—</Text>
      )}
      <View style={styles.priceProvenance}>
        <Text style={styles.priceProvenanceText}>Source · {quoteProvenance.source}</Text>
        <Text style={styles.priceProvenanceText}>{quoteProvenance.timestamp}</Text>
        <Text style={styles.priceProvenanceText}>Freshness · {quoteProvenance.freshness}</Text>
        <Text style={styles.priceProvenanceText}>Curve source · {curveSource}</Text>
      </View>
      {quoteProvenance.warning ? (
        <View accessibilityLiveRegion="assertive" style={styles.priceWarning}>
          <Text style={styles.priceWarningTitle}>Research warning</Text>
          <Text style={styles.priceWarningText}>{quoteProvenance.warning}</Text>
        </View>
      ) : null}
      {hasPriceCurve ? (
        <InteractivePriceChart
          ticker={ticker}
          dailyPrices={dailyPrices}
          weeklyPrices={weeklyPrices}
          hasDailyPriceCurve={quoteProvenance.hasDailyPriceCurve}
          hasWeeklyPriceCurve={quoteProvenance.hasWeeklyPriceCurve}
          initialRange={initialRange}
        />
      ) : (
        <View style={styles.chartUnavailable}>
          <Text style={styles.chartUnavailableText}>{historyExplanation}</Text>
        </View>
      )}
    </View>
  );
}

function SignalSnapshot({
  availability,
  indicators,
  hasAnyTechnicalData,
  historyExplanation,
  hasVerifiedMarketData,
  isSimulated,
}: {
  availability: TechnicalIndicators["availability"];
  indicators: TechnicalIndicators;
  hasAnyTechnicalData: boolean;
  historyExplanation: string;
  hasVerifiedMarketData: boolean;
  isSimulated: boolean;
}) {
  return (
    <View style={workspaceStyles.snapshotPanel}>
      <SectionHeader title="Signal snapshot" meta="technical agent" />
      <View style={workspaceStyles.readinessMeta}>
        <Text style={styles.cardLabel}>DATA READINESS</Text>
        <Text style={styles.mutedText}>
          {isSimulated
            ? "SIMULATED REVIEW DATA · NOT A MARKET PRICE"
            : hasVerifiedMarketData
              ? "Verified historical market data"
              : "Historical market-data verification pending"}
        </Text>
        <Text style={styles.mutedText}>{historyExplanation}</Text>
      </View>
      {hasAnyTechnicalData ? (
        <>
          <View style={styles.metricGrid}>
            <Metric label="RSI" value={availability?.rsi ? indicators.rsi.toFixed(1) : "—"} />
            <Metric label="MACD" value={availability?.macd ? indicators.macd.toFixed(2) : "—"} />
            <Metric label="MA20" value={availability?.moving_average_20 ? indicators.moving_average_20.toFixed(2) : "—"} />
            <Metric label="Volatility" value={availability?.volatility ? indicators.volatility.toFixed(1) + "%" : "—"} />
          </View>
          <View style={styles.signalCard}><Text style={styles.signalText}>{indicators.signal_summary}</Text></View>
        </>
      ) : (
        <View style={styles.signalUnavailable}>
          <Text style={styles.signalUnavailableTitle}>Technical signals are paused</Text>
          <Text style={styles.signalUnavailableText}>{historyExplanation}</Text>
        </View>
      )}
    </View>
  );
}

function ResearchActions({ onDebate, onEvidence }: { onDebate: () => void; onEvidence: () => void }) {
  return (
    <View style={styles.actionRow}>
      <FocusablePressable accessibilityHint="Opens the dated evidence used by the research workflow." accessibilityRole="button" style={styles.secondaryButton} onPress={onEvidence}>
        <Text style={styles.secondaryButtonText}>Evidence board</Text>
      </FocusablePressable>
      <FocusablePressable accessibilityHint="Starts Bull vs Bear for this research-ready security." accessibilityRole="button" style={styles.primaryButton} onPress={onDebate}>
        <Text style={styles.primaryButtonText}>Start Bull vs Bear →</Text>
      </FocusablePressable>
    </View>
  );
}

type ChartRange = "1M" | "3M" | "6M" | "1Y";

type InteractivePricePoint = {
  date: string;
  close: number;
  frequency: "daily" | "weekly";
  source: "daily_market_cache" | "demo_fallback" | "review_fixture" | "alpha_vantage_weekly";
  ma20: number | null;
  ma50: number | null;
  is_stale?: boolean;
  retrieved_at?: string;
};

function InteractivePriceChart({
  ticker,
  dailyPrices,
  weeklyPrices,
  hasDailyPriceCurve,
  hasWeeklyPriceCurve,
  initialRange,
}: {
  ticker: string;
  dailyPrices: StockBundle["prices"];
  weeklyPrices: StockBundle["weekly_history"];
  hasDailyPriceCurve: boolean;
  hasWeeklyPriceCurve: boolean;
  initialRange: ChartRange;
}) {
  const [range, setRange] = useState<ChartRange>(initialRange);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [chartWidth, setChartWidth] = useState(320);
  const isDailyRange = range === "1M" || range === "3M";
  const rangeIsAvailable = (option: ChartRange) => (
    option === "1M" || option === "3M" ? hasDailyPriceCurve : hasWeeklyPriceCurve
  );
  const points: InteractivePricePoint[] = useMemo(() => {
    const source = !rangeIsAvailable(range)
      ? []
      : isDailyRange
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
  }, [dailyPrices, hasDailyPriceCurve, hasWeeklyPriceCurve, isDailyRange, range, weeklyPrices]);
  const priceTrend = seriesTrend(points.map((point) => ({ date: point.date, value: point.close })));
  const width = Math.max(chartWidth, 1);
  const height = 154;
  const padding = { top: 14, right: 12, bottom: 26, left: 12 };
  if (points.length < 2) {
    return (
      <View style={styles.lineChart}>
        <View style={styles.chartHeader}>
          <Text style={styles.chartLabel}>PRICE HISTORY</Text>
          <Text style={styles.chartRange}>{range}</Text>
        </View>
        <View accessibilityRole="tablist" style={styles.rangeSelector}>
          {(["1M", "3M", "6M", "1Y"] as ChartRange[]).map((option) => (
            <FocusablePressable
              key={option}
              accessibilityLabel={`Show ${option} price history`}
              accessibilityRole="tab"
              accessibilityState={{ disabled: !rangeIsAvailable(option), selected: option === range }}
              disabled={!rangeIsAvailable(option)}
              style={[styles.rangeButton, option === range && styles.rangeButtonActive, !rangeIsAvailable(option) && styles.chartStepDisabled]}
              onPress={() => { setRange(option); setSelectedIndex(-1); }}
            >
              <Text style={[styles.rangeButtonText, option === range && styles.rangeButtonTextActive]}>{option}</Text>
            </FocusablePressable>
          ))}
        </View>
        <Text accessibilityLiveRegion="polite" style={styles.chartUnavailableText}>No labelled {range === "1M" || range === "3M" ? "daily" : "weekly"} history is available yet. Choose another range when data is available.</Text>
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
  const moveSelection = (direction: -1 | 1) => {
    setSelectedIndex((current) => {
      const resolved = current < 0 ? points.length - 1 : current;
      return Math.min(points.length - 1, Math.max(0, resolved + direction));
    });
  };
  const frequencyLabel = activePoint.frequency === "daily"
    ? activePoint.source === "review_fixture"
      ? "Simulated review fixture · not live market data"
      : activePoint.source === "daily_market_cache"
        ? activePoint.is_stale
          ? "Daily market cache · stale"
          : "Daily market cache · verified"
        : "Demo fallback · not verified market data"
    : activePoint.source === "review_fixture"
      ? "Simulated review fixture · not live market data"
      : activePoint.retrieved_at
        ? `Weekly Alpha Vantage history · refreshed ${formatQuoteTime(activePoint.retrieved_at)}`
        : "Weekly Alpha Vantage history";
  const trendSummary = describeTrend(`${ticker} ${range} price`, priceTrend, "$", "");

  return (
    <View style={styles.lineChart}>
      <View style={styles.chartHeader}>
        <Text style={styles.chartLabel}>{activePoint.frequency.toUpperCase()} PRICE · {range}</Text>
        <Text style={styles.chartRange}>{formatChartDate(points[0].date)} – {formatChartDate(points[points.length - 1].date)}</Text>
      </View>
      <View style={styles.priceChartLegend}>
        <Text style={styles.priceLegendClose}>Solid line · Close</Text>
        <Text style={styles.priceLegendMa20}>Solid line · MA20{movingAverageUnit}</Text>
        <Text style={styles.priceLegendMa50}>Dashed line · MA50{movingAverageUnit}</Text>
      </View>
      <Text style={styles.chartTextSummary}>{trendSummary}</Text>
      <View accessibilityRole="tablist" style={styles.rangeSelector}>
        {(["1M", "3M", "6M", "1Y"] as ChartRange[]).map((option) => (
          <FocusablePressable
            key={option}
            accessibilityLabel={`Show ${option} price history`}
            accessibilityRole="tab"
            accessibilityState={{ disabled: !rangeIsAvailable(option), selected: option === range }}
            disabled={!rangeIsAvailable(option)}
            style={[styles.rangeButton, option === range && styles.rangeButtonActive, !rangeIsAvailable(option) && styles.chartStepDisabled]}
            onPress={() => { setRange(option); setSelectedIndex(-1); }}
          >
            <Text style={[styles.rangeButtonText, option === range && styles.rangeButtonTextActive]}>{option}</Text>
          </FocusablePressable>
        ))}
      </View>
      <FocusablePressable
        accessibilityActions={[
          { name: "decrement", label: "Inspect earlier price point" },
          { name: "increment", label: "Inspect later price point" },
        ]}
        accessibilityHint="Use the Earlier and Later buttons, or an assistive technology increment and decrement action, to inspect a selected price point."
        accessibilityLabel={`${ticker} ${range} price chart. ${trendSummary}`}
        accessibilityRole="adjustable"
        accessibilityValue={{ max: points.length, min: 1, now: activeIndex + 1, text: `${formatMarketDate(activePoint.date)}, $${activePoint.close.toFixed(2)}` }}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === "decrement") moveSelection(-1);
          if (event.nativeEvent.actionName === "increment") moveSelection(1);
        }}
        onPress={() => setSelectedIndex(activeIndex)}
        onPointerMove={(event) => {
          if (event.nativeEvent.pointerType === "mouse") {
            setPointFromLocation(event.nativeEvent.offsetX);
          }
        }}
        style={styles.chartTouchArea}
        onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}
        {...panResponder.panHandlers}
      >
        <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image">
          <Defs>
            <LinearGradient id="price-area" x1="0" x2="0" y1="0" y2="1">
              <Stop offset="0" stopColor={colors.chart.priceArea} stopOpacity="0.46" />
              <Stop offset="1" stopColor={colors.chart.priceArea} stopOpacity="0" />
            </LinearGradient>
          </Defs>
          {[0.25, 0.5, 0.75].map((position) => (
            <Line
              key={position}
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + plotHeight * position}
              y2={padding.top + plotHeight * position}
              stroke={colors.chart.grid}
              strokeOpacity="0.16"
              strokeDasharray="4 4"
            />
          ))}
          <Path d={areaPath} fill="url(#price-area)" />
          <Path d={linePath} fill="none" stroke={colors.chart.price} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <Path d={ma20Path} fill="none" stroke={colors.chart.movingAverageShort} strokeWidth="2" strokeLinecap="round" />
          <Path d={ma50Path} fill="none" stroke={colors.chart.movingAverageLong} strokeWidth="2" strokeLinecap="round" strokeDasharray="5 3" />
          <Line x1={activeCoordinate.x} x2={activeCoordinate.x} y1={padding.top} y2={height - padding.bottom} stroke={colors.content.primary} strokeOpacity="0.7" strokeDasharray="3 3" />
          <Circle cx={activeCoordinate.x} cy={activeCoordinate.y} r="5" fill={colors.content.primary} />
          <Circle cx={activeCoordinate.x} cy={activeCoordinate.y} r="2.5" fill={colors.action.primary} />
        </Svg>
      </FocusablePressable>
      <View style={styles.chartAxis}>
        <Text style={styles.chartAxisText}>${minClose.toFixed(2)}</Text>
        <Text style={styles.chartAxisText}>${maxClose.toFixed(2)}</Text>
      </View>
      <View accessibilityLiveRegion="polite" style={styles.chartTooltip}>
        <Text style={styles.chartTooltipPrice}>${activePoint.close.toFixed(2)}</Text>
        <Text style={styles.chartTooltipMeta}>Selected point {activeIndex + 1} of {points.length} · {formatMarketDate(activePoint.date)} · {frequencyLabel}</Text>
        <Text style={styles.chartTooltipMeta}>
          MA20{movingAverageUnit} {activePoint.ma20 === null ? "not enough history" : `$${activePoint.ma20.toFixed(2)}`}
          {" · "}
          MA50{movingAverageUnit} {activePoint.ma50 === null ? "not enough history" : `$${activePoint.ma50.toFixed(2)}`}
        </Text>
      </View>
      <View style={styles.chartInspector}>
        <FocusablePressable
          accessibilityRole="button"
          accessibilityLabel="Inspect earlier price point"
          disabled={activeIndex === 0}
          style={[styles.chartStepButton, activeIndex === 0 && styles.chartStepDisabled]}
          onPress={() => moveSelection(-1)}
        >
          <Text style={styles.chartStepText}>← Earlier</Text>
        </FocusablePressable>
        <FocusablePressable
          accessibilityRole="button"
          accessibilityLabel="Inspect later price point"
          disabled={activeIndex === points.length - 1}
          style={[styles.chartStepButton, activeIndex === points.length - 1 && styles.chartStepDisabled]}
          onPress={() => moveSelection(1)}
        >
          <Text style={styles.chartStepText}>Later →</Text>
        </FocusablePressable>
      </View>
    </View>
  );
}

function TechnicalPanels({
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
    const toPoints = (values: Array<number | null>): SeriesPoint[] => values.map((value, index) => ({ date: prices[index].date, value }));
    const { macd, signal } = calculateMacd(closes);
    return {
      ma20: toPoints(simpleMovingAverage(closes, 20)),
      ma50: toPoints(simpleMovingAverage(closes, 50)),
      rsi: toPoints(calculateRsi(closes)),
      macd: toPoints(macd),
      macdSignal: toPoints(signal),
      histogram: toPoints(macd.map((value, index) => (
        value === null || signal[index] === null ? null : value - signal[index]
      ))),
      volume: prices.map((point) => ({ date: point.date, value: point.volume })),
      volatility: toPoints(calculateVolatility(closes)),
    };
  }, [prices]);
  const hasAvailableSeries = Boolean(availability && Object.values(availability).some(Boolean));
  const latestDate = hasAvailableSeries ? prices[prices.length - 1]?.date : null;
  return (
    <View style={styles.technicalPanels}>
      <SectionHeader
        title="Continuous technical panels"
        meta={latestDate ? `as of ${formatMarketDate(latestDate)}` : "availability-gated daily history"}
      />
      <ResponsiveChartGrid columns={chartColumns}>
        <ChartGridItem columns={chartColumns}>
          {availability?.moving_average_20 || availability?.moving_average_50 ? (
            <TechnicalLineChart
              title="Moving averages"
              subtitle="MA20 / MA50 · daily closes"
              series={[
                ...(availability.moving_average_20 ? [{ label: "MA20", color: palette.bull, points: data.ma20 }] : []),
                ...(availability.moving_average_50 ? [{ label: "MA50", color: palette.signal, points: data.ma50 }] : []),
              ]}
            />
          ) : <ChartEmptyState title="Moving averages" message="MA20 and MA50 need labelled daily history before they can be shown." />}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.rsi ? (
            <TechnicalLineChart
              title="Relative strength"
              subtitle="RSI 14 · 30 / 70 reference lines"
              series={[{ label: "RSI", color: colors.chart.oscillator, points: data.rsi }]}
              references={[30, 70]}
              fixedDomain={[0, 100]}
            />
          ) : <ChartEmptyState title="Relative strength" message="RSI needs labelled daily history before it can be shown." />}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.macd || availability?.macd_signal ? (
            <MacdChart
              macd={availability.macd ? data.macd : data.macd.map((point) => ({ ...point, value: null }))}
              signal={availability.macd_signal ? data.macdSignal : data.macdSignal.map((point) => ({ ...point, value: null }))}
              histogram={availability.macd && availability.macd_signal ? data.histogram : data.histogram.map((point) => ({ ...point, value: null }))}
            />
          ) : <ChartEmptyState title="MACD" message="MACD and its signal line need labelled daily history before they can be shown." />}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.volume ? (
            <TechnicalBarChart title="Daily volume" subtitle="Shares traded" points={data.volume} color={colors.chart.volume} />
          ) : <ChartEmptyState title="Daily volume" message="Volume needs labelled daily history before it can be shown." />}
        </ChartGridItem>
        <ChartGridItem columns={chartColumns}>
          {availability?.volatility ? (
            <TechnicalLineChart
              title="Annualised volatility"
              subtitle="20-session realised volatility"
              series={[{ label: "Volatility", color: palette.bear, points: data.volatility }]}
              suffix="%"
            />
          ) : <ChartEmptyState title="Annualised volatility" message="Volatility needs labelled daily history before it can be shown." />}
        </ChartGridItem>
      </ResponsiveChartGrid>
    </View>
  );
}

function MacroContextPanel({ context, chartColumns }: { context: StockBundle["macro_context"]; chartColumns: 1 | 2 }) {
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
      <SectionHeader
        title="Market backdrop"
        meta={Object.values(charts).some((chart) => chart?.simulated)
          ? "SIMULATED REVIEW FIXTURE"
          : "cached daily context"}
      />
      <View style={styles.macroDisclosure}>
        <Text style={styles.macroDisclosureTitle}>Background, not a price-move explanation</Text>
        <Text style={styles.macroDisclosureText}>These dated market series can frame broad conditions. They do not prove why a security moved on a particular day and are not personal investment advice.</Text>
      </View>
      <ResponsiveChartGrid columns={chartColumns}>
      {charts.sp500 ? (
        <ChartGridItem columns={chartColumns}>
        <TechnicalLineChart
          title={`${charts.sp500.label} · ${formatMacroValue(charts.sp500.latest.value ?? 0, charts.sp500.unit)}`}
          subtitle={`${charts.sp500.simulated ? "REVIEW FIXTURE (SIMULATED)" : charts.sp500.source.toUpperCase()} · latest ${formatMarketDate(charts.sp500.latest.date)} · last 30 observations`}
          series={[{ label: charts.sp500.label, color: colors.chart.positive, points: charts.sp500.points }]}
        />
        </ChartGridItem>
      ) : null}
      {charts.vix ? (
        <ChartGridItem columns={chartColumns}>
        <TechnicalLineChart
          title={`${charts.vix.label} · ${formatMacroValue(charts.vix.latest.value ?? 0, charts.vix.unit)}`}
          subtitle={`${charts.vix.simulated ? "REVIEW FIXTURE (SIMULATED)" : charts.vix.source.toUpperCase()} · latest ${formatMarketDate(charts.vix.latest.date)} · last 30 observations`}
          series={[{ label: charts.vix.label, color: colors.chart.oscillator, points: charts.vix.points }]}
        />
        </ChartGridItem>
      ) : null}
      {rateSeries.length ? (
        <ChartGridItem columns={chartColumns}>
        <TechnicalLineChart
          title="U.S. rates"
          subtitle={`${rateSeries.some((chart) => chart.simulated) ? "REVIEW FIXTURE (SIMULATED) · " : ""}${rateLatest}`}
          series={rateSeries.map((chart, index) => ({
            label: chart.label,
            color: [colors.action.primary, colors.chart.volume, colors.chart.positive, colors.chart.oscillator][index],
            points: chart.points,
          }))}
          suffix="%"
        />
        </ChartGridItem>
      ) : null}
      {charts.wti ? (
        <ChartGridItem columns={chartColumns}>
        <TechnicalLineChart
          title={`${charts.wti.label} · ${formatMacroValue(charts.wti.latest.value ?? 0, charts.wti.unit)}`}
          subtitle={`${charts.wti.simulated ? "REVIEW FIXTURE (SIMULATED)" : charts.wti.source.toUpperCase()} · latest ${formatMarketDate(charts.wti.latest.date)} · last 30 observations`}
          series={[{ label: charts.wti.label, color: colors.chart.negative, points: charts.wti.points }]}
          prefix="$"
        />
        </ChartGridItem>
      ) : null}
      </ResponsiveChartGrid>
    </View>
  );
}

function ResponsiveChartGrid({ columns, children }: { columns: 1 | 2; children: React.ReactNode }) {
  return <View style={[workspaceStyles.chartGrid, columns === 2 && workspaceStyles.chartGridWide]}>{children}</View>;
}

function ChartGridItem({ columns, children }: { columns: 1 | 2; children: React.ReactNode }) {
  return <View style={[workspaceStyles.chartGridItem, columns === 2 && workspaceStyles.chartGridItemWide]}>{children}</View>;
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
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 122;
  const padding = 16;
  const allPoints = series.map((item) => item.points);
  const hasData = allPoints.some((points) => points.some((point) => point.value !== null));
  if (!hasData) {
    return <ChartEmptyState title={title} message={`No labelled values are available for ${title.toLowerCase()} yet.`} />;
  }
  const { min, max } = chartScale(allPoints, references, fixedDomain);
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) => padding + (1 - (value - min) / Math.max(max - min, 0.0001)) * plotHeight;
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}>
        <View><Text style={styles.cardTitle}>{title}</Text><Text style={styles.mutedText}>{subtitle}</Text></View>
        <Text style={styles.chartLegend}>{series.map((item) => item.label).join(" · ")}</Text>
      </View>
      {series.map((item) => (
        <View key={`${item.label}-summary`}>
          <Text style={[styles.chartTextSummary, styles.technicalChartSummary]}>
            {describeTrend(item.label, seriesTrend(item.points), prefix, suffix)}
          </Text>
          <Text style={styles.chartNumericText}>{describeLatest(item.label, item.points, prefix, suffix)}</Text>
        </View>
      ))}
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel={`${title}. ${subtitle}.`}>
          {[0.25, 0.5, 0.75].map((position) => <Line key={position} x1={padding} x2={width - padding} y1={padding + plotHeight * position} y2={padding + plotHeight * position} stroke={colors.chart.grid} strokeDasharray="3 4" />)}
          {references.map((value) => <Line key={value} x1={padding} x2={width - padding} y1={yForValue(value)} y2={yForValue(value)} stroke={colors.chart.reference} strokeDasharray="5 4" />)}
          {series.map((item) => <Path key={item.label} d={technicalPath(item.points, min, max, width, height, padding)} fill="none" stroke={item.color} strokeWidth="2.5" strokeLinecap="round" />)}
        </Svg>
      </View>
      <View style={styles.chartNumericAxis}><Text style={styles.chartNumericText}>{prefix}{min.toFixed(1)}{suffix}</Text><Text style={styles.chartNumericText}>{prefix}{max.toFixed(1)}{suffix}</Text></View>
    </View>
  );
}

function MacdChart({ macd, signal, histogram }: { macd: SeriesPoint[]; signal: SeriesPoint[]; histogram: SeriesPoint[] }) {
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 128;
  const padding = 16;
  const hasData = [macd, signal, histogram].some((series) => series.some((point) => point.value !== null));
  if (!hasData) return <ChartEmptyState title="MACD" message="No labelled MACD values are available yet." />;
  const { min, max } = chartScale([macd, signal, histogram], [0]);
  const range = Math.max(max - min, 0.0001);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const yForValue = (value: number) => padding + (1 - (value - min) / range) * plotHeight;
  const baseline = yForValue(0);
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>MACD</Text><Text style={styles.mutedText}>MACD / signal lines · histogram</Text></View><Text style={styles.chartLegend}>MACD · Signal</Text></View>
      {macd.some((point) => point.value !== null) ? <Text style={[styles.chartTextSummary, styles.technicalChartSummary]}>{describeTrend("MACD", seriesTrend(macd))} {describeLatest("MACD", macd)}</Text> : null}
      {signal.some((point) => point.value !== null) ? <Text style={[styles.chartTextSummary, styles.technicalChartSummary]}>{describeTrend("Signal", seriesTrend(signal))} {describeLatest("Signal", signal)}</Text> : null}
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel="MACD and signal line chart with a positive or negative histogram.">
          <Line x1={padding} x2={width - padding} y1={baseline} y2={baseline} stroke={colors.chart.reference} strokeDasharray="5 4" />
          {histogram.map((point, index) => {
            if (point.value === null) return null;
            const x = padding + (index / Math.max(histogram.length - 1, 1)) * plotWidth;
            const y = yForValue(point.value);
            return <Rect key={point.date} x={x - 1.5} y={Math.min(y, baseline)} width={3} height={Math.abs(y - baseline)} fill={point.value >= 0 ? colors.chart.positive : colors.chart.negative} />;
          })}
          <Path d={technicalPath(macd, min, max, width, height, padding)} fill="none" stroke={colors.chart.oscillator} strokeWidth="2.3" />
          <Path d={technicalPath(signal, min, max, width, height, padding)} fill="none" stroke={palette.signal} strokeWidth="2.3" />
        </Svg>
      </View>
      <View style={styles.chartNumericAxis}><Text style={styles.chartNumericText}>{min.toFixed(2)}</Text><Text style={styles.chartNumericText}>{max.toFixed(2)}</Text></View>
    </View>
  );
}

function TechnicalBarChart({ title, subtitle, points, color }: { title: string; subtitle: string; points: SeriesPoint[]; color: string }) {
  const [chartWidth, setChartWidth] = useState(320);
  const width = Math.max(chartWidth, 1);
  const height = 104;
  const padding = 16;
  const values = points.flatMap((point) => point.value === null ? [] : [point.value]);
  if (!values.length) return <ChartEmptyState title={title} message={`No labelled values are available for ${title.toLowerCase()} yet.`} />;
  const max = Math.max(...values);
  const scaleMax = chartBarScaleMaximum(values);
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  return (
    <View style={styles.technicalChartCard}>
      <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>{title}</Text><Text style={styles.mutedText}>{subtitle}</Text></View><Text style={styles.chartLegend}>max {(max / 1_000_000).toFixed(1)}M</Text></View>
      <Text style={[styles.chartTextSummary, styles.technicalChartSummary]}>{describeTrend(title, seriesTrend(points))}</Text>
      <Text style={styles.chartNumericText}>{describeLatest(title, points, "", "", (value) => `${(value / 1_000_000).toFixed(1)}M shares`)}</Text>
      <View onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}>
        <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityRole="image" accessibilityLabel={`${title}. ${subtitle}.`}>
          {points.map((point, index) => {
            if (point.value === null) return null;
            const barWidth = Math.max(1.5, plotWidth / points.length - 1);
            const x = padding + (index / points.length) * plotWidth;
            const barHeight = (point.value / scaleMax) * plotHeight;
            return <Rect key={point.date} x={x} y={height - padding - barHeight} width={barWidth} height={barHeight} fill={color} opacity={0.78} />;
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

function describeTrend(label: string, trend: ReturnType<typeof seriesTrend>, prefix = "", suffix = ""): string {
  if (!trend) return `${label} trend is unavailable because fewer than two labelled values are available.`;
  const direction = trend.direction === "up" ? "rose" : trend.direction === "down" ? "fell" : "was unchanged";
  const absoluteChange = `${prefix}${Math.abs(trend.absoluteChange).toFixed(2)}${suffix}`;
  const percentage = trend.percentChange === null ? "percentage change unavailable" : `${Math.abs(trend.percentChange).toFixed(1)}%`;
  return `${label} ${direction} by ${absoluteChange} (${percentage}) from ${formatMarketDate(trend.startDate)} to ${formatMarketDate(trend.endDate)}.`;
}

function describeLatest(
  label: string,
  points: SeriesPoint[],
  prefix = "",
  suffix = "",
  formatValue?: (value: number) => string,
): string {
  const latest = [...points].reverse().find((point) => point.value !== null);
  return latest?.value === null || latest === undefined
    ? `${label} latest value is unavailable.`
    : `Latest · ${formatValue ? formatValue(latest.value) : `${prefix}${latest.value.toFixed(2)}${suffix}`} · ${formatMarketDate(latest.date)}`;
}

const workspaceStyles = StyleSheet.create({
  overview: { minWidth: 0 },
  overviewDesktop: { alignItems: "flex-start", flexDirection: "row", gap: spacing.lg },
  primaryColumn: { flex: 1, minWidth: 0 },
  readinessSidebar: {
    backgroundColor: colors.surface.raised,
    borderColor: colors.border.subtle,
    borderRadius: radii.lg,
    borderWidth: 1,
    flexBasis: 320,
    flexGrow: 0,
    flexShrink: 1,
    minWidth: 0,
    padding: spacing.lg,
  },
  snapshotPanel: { minWidth: 0 },
  readinessMeta: {
    backgroundColor: colors.surface.subtle,
    borderColor: colors.border.subtle,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.xs,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  chartGrid: { minWidth: 0 },
  chartGridWide: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  chartGridItem: { minWidth: 0 },
  chartGridItemWide: { flexBasis: "48%", flexGrow: 1, minWidth: 0 },
});
