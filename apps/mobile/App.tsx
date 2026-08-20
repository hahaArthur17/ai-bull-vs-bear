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
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from "react-native-svg";

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
    if (range === "1M") {
      return dailyPrices.slice(-22).map((point) => ({ ...point, frequency: "daily" as const }));
    }
    if (range === "3M") {
      return dailyPrices.slice(-66).map((point) => ({ ...point, frequency: "daily" as const }));
    }
    const weeklyLimit = range === "6M" ? 27 : 53;
    return weeklyPrices.slice(-weeklyLimit).map((point) => ({ ...point }));
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
  const closes = points.map((point) => point.close);
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
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
  const first = coordinates[0];
  const last = coordinates[coordinates.length - 1];
  const areaPath = `${linePath} L${last.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} L${first.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} Z`;
  const activeIndex = Math.min(Math.max(selectedIndex < 0 ? points.length - 1 : selectedIndex, 0), points.length - 1);
  const activePoint = points[activeIndex];
  const activeCoordinate = coordinates[activeIndex];
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
  const frequencyLabel = activePoint.frequency === "daily" ? "Daily market cache" : "Weekly Alpha Vantage history";

  return (
    <View
      style={styles.lineChart}
      accessibilityLabel={`AAPL ${range} price chart. Selected ${activePoint.frequency} close: ${formatMarketDate(activePoint.date)}, $${activePoint.close.toFixed(2)}. Drag across the chart or use Earlier and Later buttons to inspect points.`}
    >
      <View style={styles.chartHeader}>
        <Text style={styles.chartLabel}>{activePoint.frequency.toUpperCase()} PRICE · {range}</Text>
        <Text style={styles.chartRange}>{formatChartDate(points[0].date)} – {formatChartDate(points[points.length - 1].date)}</Text>
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
          <ClaimCard claim={analysis.bull} onExamine={onExamine} />
          <ClaimCard claim={analysis.bear} onExamine={onExamine} />
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

function ClaimCard({ claim, onExamine }: { claim: Claim; onExamine: (claim: Claim) => void }) {
  const isBull = claim.agent === "bull";
  return (
    <View style={[styles.claimCard, { borderLeftColor: isBull ? palette.bull : palette.bear }]}>
      <View style={styles.rowBetween}><Text style={[styles.cardLabel, { color: isBull ? palette.bull : palette.bear }]}>{isBull ? "BULL AGENT" : "BEAR AGENT"}</Text><Text style={styles.mutedText}>{claim.confidence} confidence</Text></View>
      <Text style={styles.claimText}>{claim.text}</Text>
      <Text style={styles.evidenceIds}>Evidence · {claim.evidence_ids.join(" + ")}</Text>
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
  evidenceIds: { color: palette.muted, fontSize: 12, marginBottom: 12 },
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
