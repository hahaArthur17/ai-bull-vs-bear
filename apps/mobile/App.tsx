import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  Text,
  View,
} from "react-native";

import { api } from "./src/api";
import { AuthScreen } from "./src/AuthScreen";
import {
  BackButton,
  LoadingView,
  NavButton,
} from "./src/components/common";
import { formatMarketDate } from "./src/dateFormat";
import { AboutScreen } from "./src/screens/AboutScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import { LiveDebateScreen } from "./src/screens/LiveDebateScreen";
import { EvidenceScreen } from "./src/screens/EvidenceScreen";
import { ExaminationScreen } from "./src/screens/ExaminationScreen";
import { StockDetailScreen } from "./src/screens/StockDetailScreen";
import { WatchlistScreen } from "./src/screens/WatchlistScreen";
import { formatMacroValue } from "./src/research/chartMath";
import { loadStockDetail } from "./src/stockDetail";
import { isSupabaseConfigured, supabase } from "./src/supabase";
import { appStyles as styles, palette } from "./src/theme";
import type {
  AnalysisResponse,
  Claim,
  DebateSessionDetail,
  DebateSessionSummary,
  EvidenceItem,
  ExaminationResponse,
  Stock,
  StockBundle,
} from "./src/types";

type Screen = "watchlist" | "stock" | "debate" | "evidence" | "examine" | "history" | "about";
type DebateExperience = "legacy" | "v2";

const DEBATE_V2_UI_ENABLED = process.env.EXPO_PUBLIC_DEBATE_V2_ENABLED === "true";

function newDebateIdempotencyKey(ticker: string): string {
  return `round1_${ticker}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function mergeStocks(...groups: Stock[][]): Stock[] {
  const byTicker = new Map<string, Stock>();
  groups.flat().forEach((stock) => byTicker.set(stock.ticker, stock));
  return [...byTicker.values()].sort((left, right) => left.ticker.localeCompare(right.ticker));
}

export default function App() {
  const [authReady, setAuthReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [screen, setScreen] = useState<Screen>("watchlist");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [selectedBundle, setSelectedBundle] = useState<StockBundle | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [liveDebate, setLiveDebate] = useState<DebateSessionDetail | null>(null);
  const [debateExperience, setDebateExperience] = useState<DebateExperience>("legacy");
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [examination, setExamination] = useState<ExaminationResponse | null>(null);
  const [history, setHistory] = useState<AnalysisResponse[]>([]);
  const [debateHistory, setDebateHistory] = useState<DebateSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debateAdmissionKey = useRef<string | null>(null);
  const stockLoadEpoch = useRef(0);

  const loadHome = async () => {
    try {
      setError("");
      const [stockResult, watchlistResult, analysisResult, debateResult] = await Promise.all([
        api.listStocks(),
        api.getWatchlist(),
        api.listAnalyses(),
        DEBATE_V2_UI_ENABLED
          ? api.listDebates().catch(() => [])
          : Promise.resolve<DebateSessionSummary[]>([]),
      ]);
      const watchedStocks = await Promise.all(
        watchlistResult.tickers.map((ticker) => api.getStock(ticker).catch(() => null)),
      );
      setStocks(mergeStocks(stockResult, watchedStocks.filter((stock): stock is Stock => stock !== null)));
      setWatchlist(watchlistResult.tickers);
      setHistory(analysisResult);
      setDebateHistory(debateResult);
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

  const searchStocks = useCallback(async (query: string): Promise<Stock[]> => {
    const results = await api.listStocks(query, 20);
    setStocks((current) => mergeStocks(current, results));
    return results;
  }, []);

  const loadSelectedStock = async (ticker: string) => {
    const requestEpoch = stockLoadEpoch.current + 1;
    stockLoadEpoch.current = requestEpoch;
    debateAdmissionKey.current = null;
    setSelectedTicker(ticker);
    setSelectedStock(null);
    setSelectedBundle(null);
    setLoading(true);
    setError("");
    try {
      const detail = await loadStockDetail(api, ticker);
      if (stockLoadEpoch.current === requestEpoch) {
        setSelectedStock(detail.stock);
        setSelectedBundle(detail.bundle);
      }
    } catch (requestError) {
      if (stockLoadEpoch.current === requestEpoch) {
        setError(requestError instanceof Error ? requestError.message : "Could not load stock details.");
      }
    } finally {
      if (stockLoadEpoch.current === requestEpoch) {
        setLoading(false);
      }
    }
  };

  const openStock = async (ticker: string) => {
    setScreen("stock");
    await loadSelectedStock(ticker);
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
    if (selectedStock && selectedStock.coverage_status !== "debate_ready") {
      setError("Bull vs Bear is available only for Debate-ready stocks.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (DEBATE_V2_UI_ENABLED) {
        debateAdmissionKey.current ||= newDebateIdempotencyKey(selectedTicker);
        const nextDebate = await api.createDebate(selectedTicker, {
          idempotencyKey: debateAdmissionKey.current,
        });
        debateAdmissionKey.current = null;
        setLiveDebate(nextDebate);
        setDebateHistory((current) => [
          nextDebate.session,
          ...current.filter((item) => item.id !== nextDebate.session.id),
        ]);
        setDebateExperience("v2");
        setScreen("debate");
        return;
      }
      const nextAnalysis = await api.runAnalysis(selectedTicker);
      setAnalysis(nextAnalysis);
      setDebateExperience("legacy");
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

  const refreshDebateHistory = async () => {
    if (!DEBATE_V2_UI_ENABLED) {
      setDebateHistory([]);
      return;
    }
    try {
      setDebateHistory(await api.listDebates());
    } catch {
      // Preserve already loaded canonical history if the optional V2 route is unavailable.
    }
  };

  const openSavedDebate = async (sessionSummary: DebateSessionSummary) => {
    let stockLoadStarted = false;
    setLoading(true);
    setError("");
    try {
      const detail = await api.getDebate(sessionSummary.id);
      setLiveDebate(detail);
      setDebateExperience("v2");
      setScreen("debate");
      stockLoadStarted = true;
      await loadSelectedStock(detail.session.ticker);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load this Debate.");
    } finally {
      if (!stockLoadStarted) setLoading(false);
    }
  };

  const renderScreen = () => {
    if (screen === "stock") {
      return (
        <StockDetailScreen
          stock={selectedStock}
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
      if (debateExperience === "v2" && liveDebate) {
        return (
          <LiveDebateScreen
            ticker={selectedTicker}
            initialDetail={liveDebate}
            onBack={() => setScreen("stock")}
          />
        );
      }
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
      return (
        <HistoryScreen
          history={history}
          debates={debateHistory}
          onOpen={(item) => {
            setSelectedTicker(item.ticker);
            setAnalysis(item);
            setDebateExperience("legacy");
            setScreen("debate");
          }}
          onOpenDebate={(sessionSummary) => void openSavedDebate(sessionSummary)}
        />
      );
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
        onSearch={searchStocks}
      />
    );
  };

  const nav = (next: Screen) => {
    if (next === "watchlist") setScreen("watchlist");
    if (next === "history") {
      setScreen("history");
      void refreshDebateHistory();
    }
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
      <StatusBar style={screen === "debate" && debateExperience === "v2" ? "light" : "dark"} />
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
            {analysis.snapshot.macro_context.length > 0 ? (
              <View style={styles.debateMacroSnapshot}>
                <Text style={styles.debateMacroLabel}>MARKET BACKGROUND AT THIS CLOSE · NOT CAUSAL</Text>
                {analysis.snapshot.macro_context.map((item) => (
                  <Text key={item.code} style={styles.debateMacroItem}>
                    {item.name} · {formatMacroValue(item.value, item.unit)} · {formatMarketDate(item.observation_date)} · {item.source.toUpperCase()}
                  </Text>
                ))}
              </View>
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
