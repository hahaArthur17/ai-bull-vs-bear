import { StatusBar } from "expo-status-bar";
import React, { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  ActivityIndicator,
  PanResponder,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop } from "react-native-svg";

import { api } from "./src/api";
import { AuthScreen } from "./src/AuthScreen";
import { isSupabaseConfigured, supabase } from "./src/supabase";
import type {
  AnalysisResponse,
  Claim,
  EvidenceItem,
  ExaminationResponse,
  Stock,
  StockBundle,
} from "./src/types";

type Screen = "watchlist" | "stock" | "debate" | "evidence" | "examine" | "history" | "about";

const palette = {
  ink: "#1e2826",
  muted: "#71807a",
  paper: "#f5f1e8",
  card: "#fffdf8",
  line: "#d8d5ca",
  signal: "#d95c3b",
  bull: "#3e8b6d",
  bear: "#b95455",
  accent: "#1d5c56",
};

export default function App() {
  const [authReady, setAuthReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [screen, setScreen] = useState<Screen>("watchlist");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [selectedBundle, setSelectedBundle] = useState<StockBundle | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [examination, setExamination] = useState<ExaminationResponse | null>(null);
  const [history, setHistory] = useState<AnalysisResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHome = async () => {
    try {
      setError("");
      const [stockResult, watchlistResult, analysisResult] = await Promise.all([
        api.listStocks(),
        api.getWatchlist(),
        api.listAnalyses(),
      ]);
      setStocks(stockResult);
      setWatchlist(watchlistResult.tickers);
      setHistory(analysisResult);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load the demo API.");
    }
  };

  useEffect(() => {
    if (!supabase) {
      setAuthReady(true);
      return;
    }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSession(data.session);
        setAuthReady(true);
      }
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setAuthReady(true);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (authReady && (!isSupabaseConfigured || session)) {
      void loadHome();
    }
  }, [authReady, session?.access_token]);

  const openStock = async (ticker: string) => {
    setSelectedTicker(ticker);
    setScreen("stock");
    setSelectedBundle(null);
    setLoading(true);
    setError("");
    try {
      setSelectedBundle(await api.getStockBundle(ticker));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load stock details.");
    } finally {
      setLoading(false);
    }
  };

  const toggleWatchlist = async (ticker: string) => {
    try {
      const next = watchlist.includes(ticker)
        ? await api.removeFromWatchlist(ticker)
        : await api.addToWatchlist(ticker);
      setWatchlist(next.tickers);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update the watchlist.");
    }
  };

  const startDebate = async () => {
    setLoading(true);
    setError("");
    try {
      const nextAnalysis = await api.runAnalysis(selectedTicker);
      setAnalysis(nextAnalysis);
      setHistory((current) => [nextAnalysis, ...current.filter((item) => item.analysis_id !== nextAnalysis.analysis_id)]);
      setScreen("debate");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not run the analysis.");
    } finally {
      setLoading(false);
    }
  };

  const openExamination = (claim: Claim) => {
    setSelectedClaim(claim);
    setExamination(null);
    setScreen("examine");
  };

  const askQuestion = async (questionType: ExaminationResponse["question_type"]) => {
    if (!selectedClaim) return;
    setLoading(true);
    try {
      setExamination(await api.examineClaim(selectedClaim.id, questionType));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not examine the claim.");
    } finally {
      setLoading(false);
    }
  };

  const renderScreen = () => {
    if (screen === "stock") {
      return (
        <StockDetailScreen
          bundle={selectedBundle}
          loading={loading}
          error={error}
          onBack={() => { setError(""); setScreen("watchlist"); }}
          onRetry={() => void openStock(selectedTicker)}
          onEvidence={() => setScreen("evidence")}
          onDebate={startDebate}
          isWatched={watchlist.includes(selectedTicker)}
          onToggleWatchlist={() => void toggleWatchlist(selectedTicker)}
        />
      );
    }
    if (screen === "debate") {
      return (
        <DebateScreen
          ticker={selectedTicker}
          analysis={analysis}
          loading={loading}
          onBack={() => setScreen("stock")}
          onExamine={openExamination}
          onRun={startDebate}
        />
      );
    }
    if (screen === "evidence") {
      return (
        <EvidenceScreen
          ticker={selectedTicker}
          evidence={analysis?.evidence || selectedBundle?.evidence || []}
          onBack={() => setScreen(analysis ? "debate" : "stock")}
        />
      );
    }
    if (screen === "examine") {
      return (
        <ExaminationScreen
          claim={selectedClaim}
          result={examination}
          loading={loading}
          onBack={() => setScreen("debate")}
          onAsk={askQuestion}
        />
      );
    }
    if (screen === "history") {
      return <HistoryScreen history={history} onOpen={(item) => { setSelectedTicker(item.ticker); setAnalysis(item); setScreen("debate"); }} />;
    }
    if (screen === "about") {
      return <AboutScreen onSignOut={supabase ? () => void supabase?.auth.signOut() : undefined} />;
    }
    return (
      <WatchlistScreen
        stocks={stocks}
        watchlist={watchlist}
        error={error}
        onOpen={openStock}
        onToggle={toggleWatchlist}
        onRetry={() => void loadHome()}
      />
    );
  };

  const nav = (next: Screen) => {
    if (next === "watchlist") setScreen("watchlist");
    if (next === "history") setScreen("history");
    if (next === "about") setScreen("about");
  };

  if (!authReady) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loading}><ActivityIndicator color={palette.accent} size="large" /></View>
      </SafeAreaView>
    );
  }
  if (isSupabaseConfigured && !session) {
    return <AuthScreen />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.appShell}>
        {error && screen !== "watchlist" && !(screen === "stock" && !selectedBundle) ? (
          <Pressable style={styles.errorBanner} onPress={() => setError("")}>
            <Text style={styles.errorText}>{error}</Text>
          </Pressable>
        ) : null}
        {renderScreen()}
        <View style={styles.bottomNav}>
          <NavButton label="Watchlist" active={screen === "watchlist"} onPress={() => nav("watchlist")} />
          <NavButton label="Signals" active={screen === "stock" || screen === "debate" || screen === "evidence" || screen === "examine"} onPress={() => void openStock(selectedTicker)} />
          <NavButton label="History" active={screen === "history"} onPress={() => nav("history")} />
          <NavButton label="About" active={screen === "about"} onPress={() => nav("about")} />
        </View>
      </View>
    </SafeAreaView>
  );
}

function WatchlistScreen({
  stocks,
  watchlist,
  error,
  onOpen,
  onToggle,
  onRetry,
}: {
  stocks: Stock[];
  watchlist: string[];
  error: string;
  onOpen: (ticker: string) => void;
  onToggle: (ticker: string) => void;
  onRetry: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () => stocks.filter((stock) => (stock.ticker + " " + stock.company_name).toLowerCase().includes(query.toLowerCase())),
    [query, stocks],
  );
  const visible = filtered.filter((stock) => watchlist.includes(stock.ticker));

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>SIGNAL / COUNTERPOINT</Text>
      <Text style={styles.heroTitle}>Make the signal legible.</Text>
      <Text style={styles.heroBody}>Educational context for stock movement, with evidence on both sides.</Text>
      {error ? (
        <View style={styles.errorCard}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.smallButton} onPress={onRetry}><Text style={styles.smallButtonText}>Retry</Text></Pressable>
        </View>
      ) : null}
      <SectionHeader title="Your watchlist" meta={visible.length + " symbols"} />
      {visible.map((stock) => (
        <StockRow key={stock.ticker} stock={stock} watched onOpen={onOpen} onToggle={onToggle} />
      ))}
      <SectionHeader title="Supported demo stocks" meta="cached data" />
      <TextInput
        placeholder="Search ticker or company"
        placeholderTextColor={palette.muted}
        value={query}
        onChangeText={setQuery}
        style={styles.search}
        autoCapitalize="characters"
      />
      {filtered.map((stock) => (
        <StockRow key={stock.ticker} stock={stock} watched={watchlist.includes(stock.ticker)} onOpen={onOpen} onToggle={onToggle} />
      ))}
      <View style={styles.disclaimerBox}>
        <Text style={styles.disclaimerText}>For educational purposes only. This app does not provide financial advice.</Text>
      </View>
    </ScrollView>
  );
}

function StockRow({
  stock,
  watched,
  onOpen,
  onToggle,
}: {
  stock: Stock;
  watched: boolean;
  onOpen: (ticker: string) => void;
  onToggle: (ticker: string) => void;
}) {
  return (
    <View style={styles.stockRow}>
      <Pressable style={styles.stockMain} onPress={() => onOpen(stock.ticker)}>
        <View style={styles.symbolBadge}><Text style={styles.symbolText}>{stock.ticker.slice(0, 1)}</Text></View>
        <View style={styles.stockCopy}>
          <Text style={styles.stockTicker}>{stock.ticker}</Text>
          <Text style={styles.stockCompany}>{stock.company_name}</Text>
        </View>
      </Pressable>
      <Pressable onPress={() => onToggle(stock.ticker)} style={styles.starButton}>
        <Text style={[styles.star, watched && styles.starActive]}>{watched ? "★" : "☆"}</Text>
      </Pressable>
    </View>
  );
}

function StockDetailScreen({
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
          <Text style={styles.detailTicker}>{bundle.stock.ticker} · {bundle.stock.sector}</Text>
        </View>
        <Pressable onPress={onToggleWatchlist}><Text style={[styles.star, isWatched && styles.starActive]}>{isWatched ? "★" : "☆"}</Text></Pressable>
      </View>
      <View style={styles.priceCard}>
        <Text style={styles.cardLabel}>{quote ? "LATEST QUOTE" : hasVerifiedMarketData ? "LATEST DAILY CLOSE" : "VERIFIED PRICE UNAVAILABLE"}</Text>
        {hasLatestQuote || hasVerifiedMarketData ? (
          <Text style={styles.priceValue}>{"$"}{(bundle.quote?.close ?? latest.close).toFixed(2)}</Text>
        ) : (
          <Text style={styles.unavailablePrice}>—</Text>
        )}
        <Text style={styles.priceMeta}>
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
        <Pressable style={styles.secondaryButton} onPress={onEvidence}><Text style={styles.secondaryButtonText}>Evidence board</Text></Pressable>
        <Pressable style={styles.primaryButton} onPress={onDebate}><Text style={styles.primaryButtonText}>Start Bull vs Bear →</Text></Pressable>
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

type SeriesPoint = { date: string; value: number | null };

function simpleMovingAverage(values: number[], period: number): Array<number | null> {
  return values.map((_, index) => {
    if (index < period - 1) return null;
    const window = values.slice(index - period + 1, index + 1);
    return window.reduce((sum, value) => sum + value, 0) / period;
  });
}

function calculateRsi(values: number[], period = 14): Array<number | null> {
  const result: Array<number | null> = values.map(() => null);
  if (values.length <= period) return result;
  let gains = 0;
  let losses = 0;
  for (let index = 1; index <= period; index += 1) {
    const change = values[index] - values[index - 1];
    gains += Math.max(0, change);
    losses += Math.max(0, -change);
  }
  let averageGain = gains / period;
  let averageLoss = losses / period;
  result[period] = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
  for (let index = period + 1; index < values.length; index += 1) {
    const change = values[index] - values[index - 1];
    averageGain = (averageGain * (period - 1) + Math.max(0, change)) / period;
    averageLoss = (averageLoss * (period - 1) + Math.max(0, -change)) / period;
    result[index] = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
  }
  return result;
}

function exponentialMovingAverage(values: number[], period: number): number[] {
  const multiplier = 2 / (period + 1);
  return values.reduce<number[]>((result, value, index) => {
    result.push(index === 0 ? value : value * multiplier + result[index - 1] * (1 - multiplier));
    return result;
  }, []);
}

function calculateVolatility(values: number[], period = 20): Array<number | null> {
  return values.map((_, index) => {
    if (index < period) return null;
    const window = values.slice(index - period, index + 1);
    const returns = window.slice(1).map((value, returnIndex) => Math.log(value / window[returnIndex]));
    const average = returns.reduce((sum, value) => sum + value, 0) / returns.length;
    const variance = returns.reduce((sum, value) => sum + (value - average) ** 2, 0) / returns.length;
    return Math.sqrt(variance) * Math.sqrt(252) * 100;
  });
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

function chartScale(
  series: SeriesPoint[][],
  references: number[] = [],
  fixedDomain?: [number, number],
) {
  const values = series.flatMap((points) => points.flatMap((point) => point.value === null ? [] : [point.value]));
  const min = fixedDomain?.[0] ?? Math.min(...values, ...references);
  const max = fixedDomain?.[1] ?? Math.max(...values, ...references);
  const padding = Math.max((max - min) * 0.12, 0.01);
  return { min: fixedDomain ? min : min - padding, max: fixedDomain ? max : max + padding };
}

function technicalPath(points: SeriesPoint[], min: number, max: number, width: number, height: number, padding: number) {
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const range = Math.max(max - min, 0.0001);
  let started = false;
  return points.map((point, index) => {
    if (point.value === null) {
      started = false;
      return "";
    }
    const x = padding + (index / Math.max(points.length - 1, 1)) * plotWidth;
    const y = padding + (1 - (point.value - min) / range) * plotHeight;
    const command = started ? "L" : "M";
    started = true;
    return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function TechnicalLineChart({
  title,
  subtitle,
  series,
  references = [],
  fixedDomain,
  suffix = "",
}: {
  title: string;
  subtitle: string;
  series: Array<{ label: string; color: string; points: SeriesPoint[] }>;
  references?: number[];
  fixedDomain?: [number, number];
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
      <View style={styles.chartNumericAxis}><Text style={styles.chartNumericText}>{min.toFixed(1)}{suffix}</Text><Text style={styles.chartNumericText}>{max.toFixed(1)}{suffix}</Text></View>
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

function formatMarketDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function formatChartDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function formatQuoteTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(value));
}

function DebateScreen({
  ticker,
  analysis,
  loading,
  onBack,
  onExamine,
  onRun,
}: {
  ticker: string;
  analysis: AnalysisResponse | null;
  loading: boolean;
  onBack: () => void;
  onExamine: (claim: Claim) => void;
  onRun: () => void;
}) {
  if (loading && !analysis) return <LoadingView label="Running the evidence workflow..." onBack={onBack} />;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <View style={styles.detailHeader}>
        <View><Text style={styles.eyebrow}>LIVE TRACE · {ticker}</Text><Text style={styles.detailTitle}>Debate Arena</Text></View>
        <Text style={styles.liveDot}>●</Text>
      </View>
      {!analysis ? (
        <View style={styles.emptyCard}>
          <Text style={styles.cardTitle}>No analysis run yet</Text>
          <Text style={styles.mutedText}>Run the deterministic demo workflow to see the Bull, Bear, Judge, and Guardrail agents.</Text>
          <Pressable style={styles.primaryButton} onPress={onRun}><Text style={styles.primaryButtonText}>Run analysis</Text></Pressable>
        </View>
      ) : (
        <>
          <View style={styles.snapshotCard}>
            <Text style={styles.cardLabel}>ANALYSIS SNAPSHOT</Text>
            <Text style={styles.snapshotTitle}>
              {formatMarketDate(analysis.snapshot.price.as_of)} close · ${analysis.snapshot.price.close.toFixed(2)}
            </Text>
            <Text style={styles.mutedText}>
              {analysis.snapshot.price.source === "daily_market_cache" && !analysis.snapshot.price.is_stale
                ? "Verified daily market cache"
                : "Price cache is unavailable or stale; interpret this run cautiously."}
            </Text>
            <Text style={styles.snapshotDetail}>
              {analysis.snapshot.included_evidence_ids.length} cited item(s)
              {analysis.snapshot.excluded_external_evidence_count > 0
                ? ` · ${analysis.snapshot.excluded_external_evidence_count} stale or undated item(s) excluded`
                : " · all retrieved external context passed its freshness check"}
            </Text>
            {analysis.snapshot.missing_current_evidence.length > 0 ? (
              <Text style={styles.snapshotWarning}>
                Missing current {analysis.snapshot.missing_current_evidence.join(" and ")} evidence.
              </Text>
            ) : null}
          </View>
          <View style={styles.judgeCard}>
            <View style={styles.rowBetween}><Text style={styles.cardLabel}>JUDGE SYNTHESIS</Text><Text style={styles.confidence}>{analysis.judge.evidence_strength} evidence</Text></View>
            <Text style={styles.judgeTitle}>{analysis.judge.summary}</Text>
            <Text style={styles.mutedText}>{analysis.judge.uncertainty}</Text>
            <Text style={styles.riskPill}>Risk level · {analysis.judge.risk_level}</Text>
          </View>
          <ClaimCard
            claim={analysis.bull}
            closeDate={analysis.snapshot.price.as_of}
            evidence={analysis.evidence}
            onExamine={onExamine}
          />
          <ClaimCard
            claim={analysis.bear}
            closeDate={analysis.snapshot.price.as_of}
            evidence={analysis.evidence}
            onExamine={onExamine}
          />
          <View style={styles.traceCard}>
            <View style={styles.rowBetween}><Text style={styles.cardLabel}>AGENT TRACE</Text><Text style={styles.mutedText}>{analysis.token_usage.model_name}</Text></View>
            {analysis.trace.map((step) => <Text key={step.step} style={styles.traceLine}>✓ {step.step.replace(/_/g, " ")} — {step.detail}</Text>)}
            <Text style={styles.traceLine}>Token ledger: {analysis.token_usage.total_tokens} demo tokens</Text>
          </View>
          <Text style={styles.safeNote}>{analysis.disclaimer}</Text>
        </>
      )}
    </ScrollView>
  );
}

function ClaimCard({
  claim,
  closeDate,
  evidence,
  onExamine,
}: {
  claim: Claim;
  closeDate: string;
  evidence: EvidenceItem[];
  onExamine: (claim: Claim) => void;
}) {
  const isBull = claim.agent === "bull";
  const evidenceById = new Map(evidence.map((item) => [item.id, item]));
  return (
    <View style={[styles.claimCard, { borderLeftColor: isBull ? palette.bull : palette.bear }]}>
      <View style={styles.rowBetween}><Text style={[styles.cardLabel, { color: isBull ? palette.bull : palette.bear }]}>{isBull ? "BULL AGENT" : "BEAR AGENT"}</Text><Text style={styles.mutedText}>{claim.confidence} confidence</Text></View>
      <Text style={styles.claimText}>{claim.text}</Text>
      <Text style={styles.claimCloseDate}>Market close · {formatMarketDate(closeDate)}</Text>
      <View style={styles.claimCitations}>
        {claim.evidence_ids.map((id) => {
          const item = evidenceById.get(id);
          const itemDate = item?.published_at ? formatMarketDate(item.published_at) : item?.source_type === "technical" ? formatMarketDate(closeDate) : "date unavailable";
          const freshness = item?.freshness.status === "current" ? "current" : item?.freshness.status === "stale" ? "stale" : "unknown";
          return <Text key={id} style={styles.evidenceIds}>Evidence · {id} · {item?.source_type ?? "unavailable"} · {itemDate} · {freshness}</Text>;
        })}
      </View>
      <Pressable onPress={() => onExamine(claim)}><Text style={styles.examineLink}>Tap to cross-examine →</Text></Pressable>
    </View>
  );
}

function EvidenceScreen({ ticker, evidence, onBack }: { ticker: string; evidence: EvidenceItem[]; onBack: () => void }) {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>{ticker} · WHAT THE AGENTS USED</Text>
      <Text style={styles.detailTitle}>Evidence Board</Text>
      {evidence.length === 0 ? <Text style={styles.mutedText}>No evidence is available yet.</Text> : evidence.map((item) => (
        <View key={item.id} style={styles.evidenceCard}>
          <View style={styles.rowBetween}><Text style={styles.evidenceTag}>{item.id}</Text><Text style={styles.mutedText}>{item.source_type}</Text></View>
          <Text style={styles.cardTitle}>{item.title}</Text>
          <Text style={styles.mutedText}>{item.excerpt}</Text>
          <Text style={styles.sourceText}>
            {typeof item.metadata.source === "string" ? item.metadata.source : "cached source"} · {item.published_at || "undated"}
          </Text>
          <Text style={[
            styles.freshnessText,
            item.freshness.status === "current" && styles.freshnessCurrent,
            item.freshness.status === "stale" && styles.freshnessStale,
          ]}>
            {item.freshness.status === "current"
              ? `Current · ${item.freshness.age_days ?? 0}d old`
              : item.freshness.status === "stale"
                ? `Stale · ${item.freshness.age_days ?? "?"}d old`
                : "Freshness unavailable"}
          </Text>
        </View>
      ))}
      <Text style={styles.safeNote}>Evidence is shown for interpretation, not as a recommendation.</Text>
    </ScrollView>
  );
}

function ExaminationScreen({
  claim,
  result,
  loading,
  onBack,
  onAsk,
}: {
  claim: Claim | null;
  result: ExaminationResponse | null;
  loading: boolean;
  onBack: () => void;
  onAsk: (questionType: ExaminationResponse["question_type"]) => void;
}) {
  if (!claim) return <LoadingView label="No claim selected." onBack={onBack} />;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>SELECTED {claim.agent.toUpperCase()} CLAIM</Text>
      <Text style={styles.detailTitle}>Cross Examination</Text>
      <View style={styles.answerCard}><Text style={styles.cardTitle}>{claim.text}</Text><Text style={styles.evidenceIds}>{claim.evidence_ids.join(" + ")}</Text></View>
      <SectionHeader title="Ask a focused question" meta="explanation agent" />
      {([
        ["evidence_support", "What evidence supports this?"],
        ["explain_term", "What does this term mean?"],
        ["signal_strength", "How strong is the signal?"],
        ["risk_meaning", "What is the risk meaning?"],
      ] as const).map(([type, label]) => (
        <Pressable key={type} style={styles.questionButton} onPress={() => onAsk(type)}><Text style={styles.questionText}>{label}</Text></Pressable>
      ))}
      {loading ? <ActivityIndicator color={palette.accent} style={styles.loader} /> : null}
      {result ? <View style={styles.answerCard}><Text style={styles.cardLabel}>ANSWER</Text><Text style={styles.answerText}>{result.answer}</Text><Text style={styles.safeNote}>{result.disclaimer}</Text></View> : null}
    </ScrollView>
  );
}

function HistoryScreen({ history, onOpen }: { history: AnalysisResponse[]; onOpen: (item: AnalysisResponse) => void }) {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>ANALYSIS RUNS</Text>
      <Text style={styles.detailTitle}>History</Text>
      {history.length === 0 ? <View style={styles.emptyCard}><Text style={styles.cardTitle}>No local runs yet</Text><Text style={styles.mutedText}>Start a Bull vs Bear debate from a stock detail page.</Text></View> : history.map((item) => (
        <Pressable key={item.analysis_id} style={styles.historyRow} onPress={() => onOpen(item)}>
          <View><Text style={styles.stockTicker}>{item.ticker}</Text><Text style={styles.mutedText}>{new Date(item.created_at).toLocaleString()}</Text></View>
          <Text style={styles.examineLink}>Open →</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function AboutScreen({ onSignOut }: { onSignOut?: () => void }) {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>ABOUT THIS DEMO</Text>
      <Text style={styles.detailTitle}>AI Bull vs Bear</Text>
      <Text style={styles.heroBody}>An educational Agentic RAG demo that places technical signals, news, filing evidence, and two competing explanations side by side.</Text>
      <View style={styles.aboutCard}><Text style={styles.cardTitle}>Safety by design</Text><Text style={styles.mutedText}>The app is designed to explain evidence and uncertainty. It does not provide buy, sell, hold, or personalised financial advice.</Text></View>
      <View style={styles.aboutCard}><Text style={styles.cardTitle}>Demo mode</Text><Text style={styles.mutedText}>The default provider uses deterministic cached data so the app can run without API keys. Supabase and model providers can be connected later through environment variables.</Text></View>
      {onSignOut ? <Pressable style={styles.secondaryButton} onPress={onSignOut}><Text style={styles.secondaryButtonText}>Sign out</Text></Pressable> : null}
    </ScrollView>
  );
}

function SectionHeader({ title, meta }: { title: string; meta: string }) {
  return <View style={styles.sectionHeader}><Text style={styles.sectionTitle}>{title}</Text><Text style={styles.mutedText}>{meta}</Text></View>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <View style={styles.metric}><Text style={styles.cardLabel}>{label}</Text><Text style={styles.metricValue}>{value}</Text></View>;
}

function BackButton({ onPress }: { onPress: () => void }) {
  return <Pressable onPress={onPress} style={styles.backButton}><Text style={styles.backText}>← Back</Text></Pressable>;
}

function LoadingView({ label, onBack }: { label: string; onBack: () => void }) {
  return <View style={styles.loading}><BackButton onPress={onBack} /><ActivityIndicator color={palette.accent} size="large" /><Text style={styles.mutedText}>{label}</Text></View>;
}

function FailureView({ message, onBack, onRetry }: { message: string; onBack: () => void; onRetry: () => void }) {
  return (
    <View style={styles.loading}>
      <BackButton onPress={onBack} />
      <View style={styles.errorCard}>
        <Text style={styles.errorText}>{message}</Text>
        <Pressable style={styles.smallButton} onPress={onRetry}><Text style={styles.smallButtonText}>Retry</Text></Pressable>
      </View>
    </View>
  );
}

function NavButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return <Pressable onPress={onPress} style={styles.navButton}><Text style={[styles.navLabel, active && styles.navLabelActive]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.paper },
  appShell: { flex: 1 },
  page: { padding: 22, paddingBottom: 110 },
  eyebrow: { color: palette.signal, fontSize: 11, fontWeight: "800", letterSpacing: 1.4, marginBottom: 8 },
  heroTitle: { color: palette.ink, fontSize: 38, lineHeight: 42, fontWeight: "800", marginBottom: 10 },
  heroBody: { color: palette.muted, fontSize: 16, lineHeight: 24, marginBottom: 26 },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 18, marginBottom: 10 },
  sectionTitle: { color: palette.ink, fontSize: 17, fontWeight: "800" },
  mutedText: { color: palette.muted, fontSize: 13, lineHeight: 20 },
  stockRow: { backgroundColor: palette.card, borderWidth: 1, borderColor: palette.line, borderRadius: 16, padding: 12, flexDirection: "row", alignItems: "center", marginBottom: 10 },
  stockMain: { flex: 1, flexDirection: "row", alignItems: "center" },
  symbolBadge: { backgroundColor: palette.accent, borderRadius: 12, width: 42, height: 42, alignItems: "center", justifyContent: "center" },
  symbolText: { color: "#fff", fontSize: 18, fontWeight: "800" },
  stockCopy: { marginLeft: 12 },
  stockTicker: { color: palette.ink, fontSize: 16, fontWeight: "800" },
  stockCompany: { color: palette.muted, fontSize: 13, marginTop: 3 },
  starButton: { padding: 8 },
  star: { color: palette.muted, fontSize: 26 },
  starActive: { color: palette.signal },
  search: { borderColor: palette.line, borderWidth: 1, borderRadius: 12, padding: 13, color: palette.ink, backgroundColor: palette.card, marginBottom: 14 },
  disclaimerBox: { padding: 16, backgroundColor: "#ebe4d3", borderRadius: 14, marginTop: 20 },
  disclaimerText: { color: palette.ink, fontSize: 12, lineHeight: 18 },
  errorCard: { padding: 14, backgroundColor: "#fae2db", borderRadius: 12, marginBottom: 14 },
  errorBanner: { backgroundColor: "#fae2db", paddingHorizontal: 16, paddingVertical: 8 },
  errorText: { color: "#8d332b", fontSize: 12, lineHeight: 18 },
  smallButton: { marginTop: 8, alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 9, backgroundColor: palette.signal },
  smallButtonText: { color: "#fff", fontWeight: "700" },
  backButton: { marginBottom: 18, alignSelf: "flex-start" },
  backText: { color: palette.accent, fontWeight: "800" },
  detailHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
  detailTitle: { color: palette.ink, fontSize: 30, fontWeight: "800", marginBottom: 6 },
  detailTicker: { color: palette.muted, fontSize: 14 },
  priceCard: { backgroundColor: palette.accent, borderRadius: 20, padding: 20, marginBottom: 22 },
  cardLabel: { color: palette.muted, fontSize: 10, fontWeight: "800", letterSpacing: 1.1, marginBottom: 7 },
  priceValue: { color: "#fffdf8", fontSize: 36, fontWeight: "800" },
  unavailablePrice: { color: "#fffdf8", fontSize: 36, fontWeight: "800", lineHeight: 43 },
  priceMeta: { color: "#c8d9d3", fontSize: 13, lineHeight: 19, marginTop: 4 },
  lineChart: { marginTop: 18 },
  chartHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 3 },
  chartLabel: { color: "#d7f0dc", fontSize: 10, fontWeight: "800", letterSpacing: 1.1 },
  chartRange: { color: "#c8d9d3", fontSize: 11 },
  priceChartLegend: { flexDirection: "row", gap: 9, marginTop: 5 },
  priceLegendClose: { color: "#d7f0dc", fontSize: 10, fontWeight: "800" },
  priceLegendMa20: { color: "#f5c86e", fontSize: 10, fontWeight: "800" },
  priceLegendMa50: { color: "#d59be3", fontSize: 10, fontWeight: "800" },
  rangeSelector: { flexDirection: "row", gap: 6, marginTop: 10, marginBottom: 10 },
  rangeButton: { borderColor: "rgba(255,255,255,0.32)", borderWidth: 1, borderRadius: 8, paddingHorizontal: 9, paddingVertical: 6 },
  rangeButtonActive: { backgroundColor: "#fffdf8", borderColor: "#fffdf8" },
  rangeButtonText: { color: "#d7f0dc", fontSize: 11, fontWeight: "800" },
  rangeButtonTextActive: { color: palette.accent },
  chartTouchArea: { minHeight: 154 },
  chartAxis: { flexDirection: "row", justifyContent: "space-between", marginTop: -4 },
  chartAxisText: { color: "#c8d9d3", fontSize: 11 },
  chartTooltip: { marginTop: 10, backgroundColor: "rgba(255,255,255,0.12)", borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 },
  chartTooltipPrice: { color: "#fffdf8", fontSize: 17, fontWeight: "800" },
  chartTooltipMeta: { color: "#d7f0dc", fontSize: 11, marginTop: 2 },
  chartInspector: { flexDirection: "row", justifyContent: "space-between", marginTop: 10 },
  chartStepButton: { borderColor: "rgba(255,255,255,0.34)", borderWidth: 1, borderRadius: 8, paddingHorizontal: 9, paddingVertical: 7 },
  chartStepDisabled: { opacity: 0.35 },
  chartStepText: { color: "#fffdf8", fontSize: 11, fontWeight: "800" },
  chartUnavailable: { height: 116, marginTop: 18, alignItems: "center", justifyContent: "center", borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,255,255,0.24)", borderStyle: "dashed", paddingHorizontal: 20 },
  chartUnavailableText: { color: "#c8d9d3", fontSize: 13, lineHeight: 19, textAlign: "center" },
  signalUnavailable: { backgroundColor: "#f3eadb", borderRadius: 14, padding: 16, marginTop: 18 },
  signalUnavailableTitle: { color: palette.ink, fontSize: 15, fontWeight: "800", marginBottom: 5 },
  signalUnavailableText: { color: palette.muted, fontSize: 13, lineHeight: 19 },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metric: { width: "47%", backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 14, padding: 14 },
  metricValue: { color: palette.ink, fontSize: 20, fontWeight: "800" },
  technicalPanels: { marginTop: 4 },
  technicalChartCard: { backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 15, padding: 14, marginBottom: 12 },
  chartLegend: { color: palette.muted, fontSize: 10, fontWeight: "800" },
  chartNumericAxis: { flexDirection: "row", justifyContent: "space-between", marginTop: -5 },
  chartNumericText: { color: palette.muted, fontSize: 10 },
  signalCard: { backgroundColor: "#e9f0e5", padding: 14, borderRadius: 14, marginVertical: 16 },
  signalText: { color: palette.accent, lineHeight: 20, fontWeight: "700" },
  actionRow: { gap: 10, marginTop: 8 },
  primaryButton: { backgroundColor: palette.signal, borderRadius: 12, padding: 15, alignItems: "center", marginTop: 14 },
  primaryButtonText: { color: "#fff", fontWeight: "800", fontSize: 14 },
  secondaryButton: { borderColor: palette.accent, borderWidth: 1, borderRadius: 12, padding: 14, alignItems: "center" },
  secondaryButtonText: { color: palette.accent, fontWeight: "800" },
  liveDot: { color: palette.signal, fontSize: 20 },
  judgeCard: { backgroundColor: "#e9f0e5", padding: 18, borderRadius: 18, marginBottom: 14 },
  snapshotCard: { backgroundColor: "#fff5e4", padding: 16, borderRadius: 16, marginBottom: 14, borderWidth: 1, borderColor: "#ead4ad" },
  snapshotTitle: { color: palette.ink, fontSize: 16, fontWeight: "800", marginBottom: 5 },
  snapshotDetail: { color: palette.muted, fontSize: 12, lineHeight: 18, marginTop: 8 },
  snapshotWarning: { color: palette.bear, fontSize: 12, fontWeight: "700", lineHeight: 18, marginTop: 6 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  confidence: { color: palette.bull, fontSize: 12, fontWeight: "700" },
  judgeTitle: { color: palette.ink, fontSize: 19, lineHeight: 25, fontWeight: "800", marginVertical: 8 },
  riskPill: { color: palette.bear, fontWeight: "700", marginTop: 10 },
  claimCard: { backgroundColor: palette.card, borderWidth: 1, borderColor: palette.line, borderLeftWidth: 5, borderRadius: 15, padding: 16, marginBottom: 12 },
  claimText: { color: palette.ink, fontSize: 15, lineHeight: 22, marginBottom: 12 },
  claimCloseDate: { color: palette.ink, fontSize: 12, fontWeight: "800", marginBottom: 7 },
  claimCitations: { gap: 4, marginBottom: 12 },
  evidenceIds: { color: palette.muted, fontSize: 11, lineHeight: 16 },
  examineLink: { color: palette.accent, fontWeight: "800", fontSize: 13 },
  traceCard: { backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 15, padding: 16, marginTop: 8 },
  traceLine: { color: palette.muted, fontSize: 12, lineHeight: 19, marginTop: 7 },
  safeNote: { color: palette.muted, fontSize: 12, lineHeight: 18, marginTop: 16 },
  evidenceCard: { backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 15, padding: 16, marginBottom: 12 },
  evidenceTag: { color: palette.signal, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  cardTitle: { color: palette.ink, fontSize: 16, fontWeight: "800", lineHeight: 22, marginBottom: 6 },
  sourceText: { color: palette.muted, fontSize: 11, marginTop: 12 },
  freshnessText: { color: palette.muted, fontSize: 11, fontWeight: "700", marginTop: 5 },
  freshnessCurrent: { color: palette.bull },
  freshnessStale: { color: palette.bear },
  answerCard: { backgroundColor: "#fff5e4", borderRadius: 15, padding: 16, marginBottom: 14 },
  questionButton: { borderColor: palette.line, borderWidth: 1, backgroundColor: palette.card, borderRadius: 12, padding: 15, marginBottom: 9 },
  questionText: { color: palette.ink, fontWeight: "700" },
  answerText: { color: palette.ink, fontSize: 15, lineHeight: 23, marginBottom: 10 },
  loader: { margin: 14 },
  emptyCard: { backgroundColor: palette.card, borderRadius: 16, padding: 20, borderColor: palette.line, borderWidth: 1 },
  historyRow: { backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 14, padding: 16, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  aboutCard: { backgroundColor: palette.card, borderColor: palette.line, borderWidth: 1, borderRadius: 16, padding: 18, marginBottom: 12 },
  loading: { flex: 1, padding: 22, alignItems: "center", justifyContent: "center", gap: 14 },
  bottomNav: { position: "absolute", bottom: 0, left: 0, right: 0, backgroundColor: palette.card, borderTopWidth: 1, borderTopColor: palette.line, flexDirection: "row", justifyContent: "space-around", paddingVertical: 13, paddingBottom: 18 },
  navButton: { paddingHorizontal: 8 },
  navLabel: { color: palette.muted, fontSize: 12, fontWeight: "700" },
  navLabelActive: { color: palette.signal },
});
