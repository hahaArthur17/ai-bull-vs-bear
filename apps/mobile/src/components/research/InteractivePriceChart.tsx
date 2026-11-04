import { useMemo, useState } from "react";
import { Text, View } from "react-native";
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from "react-native-svg";
import { formatChartDate, formatMarketDate, formatQuoteTime } from "../../dateFormat";
import { describeTrend } from "../../research/chartLabels";
import { nearestChartPointIndex, seriesTrend } from "../../research/chartMath";
import {
  buildPriceChartGeometry,
  selectPriceChartPoints,
  type ChartRange,
} from "../../research/priceChart";
import { colors, appStyles as styles } from "../../theme";
import type { StockBundle } from "../../types";
import { FocusablePressable } from "../common";

export function InteractivePriceChart({
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
  const rangeIsAvailable = (option: ChartRange) =>
    option === "1M" || option === "3M" ? hasDailyPriceCurve : hasWeeklyPriceCurve;
  const points = useMemo(
    () =>
      selectPriceChartPoints(
        dailyPrices,
        weeklyPrices,
        range,
        hasDailyPriceCurve,
        hasWeeklyPriceCurve,
      ),
    [dailyPrices, weeklyPrices, range, hasDailyPriceCurve, hasWeeklyPriceCurve],
  );
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
        <PriceRangeSelector
          range={range}
          available={rangeIsAvailable}
          onChange={(value) => {
            setRange(value);
            setSelectedIndex(-1);
          }}
        />
        <Text accessibilityLiveRegion="polite" style={styles.chartUnavailableText}>
          No labelled {range === "1M" || range === "3M" ? "daily" : "weekly"} history is available
          yet. Choose another range when data is available.
        </Text>
      </View>
    );
  }
  const geometry = buildPriceChartGeometry(points, width, height, padding);
  const { minClose, maxClose, plotHeight, coordinates, linePath, areaPath, ma20Path, ma50Path } =
    geometry;
  const activeIndex = Math.min(
    Math.max(selectedIndex < 0 ? points.length - 1 : selectedIndex, 0),
    points.length - 1,
  );
  const activePoint = points[activeIndex];
  const activeCoordinate = coordinates[activeIndex];
  const movingAverageUnit = activePoint.frequency === "daily" ? "d" : "w";
  const setPointFromLocation = (locationX: number) => {
    setSelectedIndex(
      nearestChartPointIndex(locationX, chartWidth, points.length, padding.left, padding.right),
    );
  };
  const moveSelection = (direction: -1 | 1) => {
    setSelectedIndex((current) => {
      const resolved = current < 0 ? points.length - 1 : current;
      return Math.min(points.length - 1, Math.max(0, resolved + direction));
    });
  };
  const frequencyLabel =
    activePoint.frequency === "daily"
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
        <Text style={styles.chartLabel}>
          {activePoint.frequency.toUpperCase()} PRICE · {range}
        </Text>
        <Text style={styles.chartRange}>
          {formatChartDate(points[0].date)} – {formatChartDate(points[points.length - 1].date)}
        </Text>
      </View>
      <View style={styles.priceChartLegend}>
        <Text style={styles.priceLegendClose}>Close</Text>
        <Text style={styles.priceLegendMa20}>MA20{movingAverageUnit}</Text>
        <Text style={styles.priceLegendMa50}>MA50{movingAverageUnit} · dashed</Text>
      </View>
      <PriceRangeSelector
        range={range}
        available={rangeIsAvailable}
        onChange={(value) => {
          setRange(value);
          setSelectedIndex(-1);
        }}
      />
      <FocusablePressable
        accessibilityActions={[
          { name: "decrement", label: "Inspect earlier price point" },
          { name: "increment", label: "Inspect later price point" },
        ]}
        accessibilityHint="Touch, click, or drag horizontally across the chart to inspect the nearest price point. Earlier and Later remain available for keyboard and assistive technology use."
        accessibilityLabel={`${ticker} ${range} price chart. ${trendSummary}`}
        accessibilityRole="adjustable"
        accessibilityValue={{
          max: points.length,
          min: 1,
          now: activeIndex + 1,
          text: `${formatMarketDate(activePoint.date)}, $${activePoint.close.toFixed(2)}`,
        }}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === "decrement") moveSelection(-1);
          if (event.nativeEvent.actionName === "increment") moveSelection(1);
        }}
        // The shared control owns responder handlers, so use its press lifecycle
        // for direct taps and the non-competing touch stream for horizontal drags.
        onPressIn={(event) => setPointFromLocation(event.nativeEvent.locationX)}
        onTouchMove={(event) => setPointFromLocation(event.nativeEvent.locationX)}
        onPointerMove={(event) => {
          if (event.nativeEvent.pointerType === "mouse") {
            setPointFromLocation(event.nativeEvent.offsetX);
          }
        }}
        style={styles.chartTouchArea}
        onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}
      >
        <Svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          accessibilityRole="image"
        >
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
          <Path
            d={linePath}
            fill="none"
            stroke={colors.chart.price}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <Path
            d={ma20Path}
            fill="none"
            stroke={colors.chart.movingAverageShort}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <Path
            d={ma50Path}
            fill="none"
            stroke={colors.chart.movingAverageLong}
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="5 3"
          />
          <Line
            x1={activeCoordinate.x}
            x2={activeCoordinate.x}
            y1={padding.top}
            y2={height - padding.bottom}
            stroke={colors.content.primary}
            strokeOpacity="0.7"
            strokeDasharray="3 3"
          />
          <Circle
            cx={activeCoordinate.x}
            cy={activeCoordinate.y}
            r="5"
            fill={colors.content.primary}
          />
          <Circle
            cx={activeCoordinate.x}
            cy={activeCoordinate.y}
            r="2.5"
            fill={colors.action.primary}
          />
        </Svg>
      </FocusablePressable>
      <View style={styles.chartAxis}>
        <Text style={styles.chartAxisText}>${minClose.toFixed(2)}</Text>
        <Text style={styles.chartAxisText}>${maxClose.toFixed(2)}</Text>
      </View>
      <View
        accessible
        accessibilityLabel={`Selected price details: Date ${formatMarketDate(activePoint.date)}. Close $${activePoint.close.toFixed(2)}. MA20${movingAverageUnit} ${activePoint.ma20 === null ? "not enough history" : `$${activePoint.ma20.toFixed(2)}`}. MA50${movingAverageUnit} ${activePoint.ma50 === null ? "not enough history" : `$${activePoint.ma50.toFixed(2)}`}. ${frequencyLabel}.`}
        accessibilityLiveRegion="polite"
        style={styles.chartTooltip}
      >
        <Text style={styles.chartTooltipPrice}>
          ${activePoint.close.toFixed(2)}{" "}
          <Text style={styles.chartTooltipMeta}>· {formatMarketDate(activePoint.date)}</Text>
        </Text>
        <Text style={styles.chartTooltipMeta}>
          MA20{movingAverageUnit}{" "}
          {activePoint.ma20 === null ? "not enough history" : `$${activePoint.ma20.toFixed(2)}`}
          {" · "}
          MA50{movingAverageUnit}{" "}
          {activePoint.ma50 === null ? "not enough history" : `$${activePoint.ma50.toFixed(2)}`}
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
          style={[
            styles.chartStepButton,
            activeIndex === points.length - 1 && styles.chartStepDisabled,
          ]}
          onPress={() => moveSelection(1)}
        >
          <Text style={styles.chartStepText}>Later →</Text>
        </FocusablePressable>
      </View>
    </View>
  );
}

function PriceRangeSelector({
  range,
  available,
  onChange,
}: {
  range: ChartRange;
  available: (range: ChartRange) => boolean;
  onChange: (range: ChartRange) => void;
}) {
  return (
    <View accessibilityRole="tablist" style={styles.rangeSelector}>
      {(["1M", "3M", "6M", "1Y"] as ChartRange[]).map((option) => (
        <FocusablePressable
          key={option}
          accessibilityLabel={`Show ${option} price history`}
          accessibilityRole="tab"
          accessibilityState={{
            disabled: !available(option),
            selected: option === range,
          }}
          disabled={!available(option)}
          style={[
            styles.rangeButton,
            option === range && styles.rangeButtonActive,
            !available(option) && styles.chartStepDisabled,
          ]}
          onPress={() => onChange(option)}
        >
          <Text style={[styles.rangeButtonText, option === range && styles.rangeButtonTextActive]}>
            {option}
          </Text>
        </FocusablePressable>
      ))}
    </View>
  );
}
