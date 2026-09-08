import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  ActivityIndicator,
  SafeAreaView,
  Text,
  useWindowDimensions,
  View,
} from "react-native";

import { api } from "./src/api";
import { AuthScreen } from "./src/AuthScreen";
import {
  FocusablePressable,
  NavButton,
} from "./src/components/common";
import { getResponsiveAppShellLayout } from "./src/appShell";
import { canSubmitExamination } from "./src/examinationState";
import { findActiveDebate, isActiveDebateConflict } from "./src/debateHistoryView";
import { AboutScreen } from "./src/screens/AboutScreen";
import { LegacyDebateScreen } from "./src/screens/LegacyDebateScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import { LiveDebateScreen } from "./src/screens/LiveDebateScreen";
import { EvidenceScreen } from "./src/screens/EvidenceScreen";
import { ExaminationScreen } from "./src/screens/ExaminationScreen";
import { StockDetailScreen } from "./src/screens/StockDetailScreen";
import { WatchlistScreen } from "./src/screens/WatchlistScreen";
import { loadStockDetail } from "./src/stockDetail";
import { isSupabaseConfigured, supabase } from "./src/supabase";
import { appStyles as styles, palette } from "./src/theme";
import type {
  AnalysisResponse,
  Claim,
  DebateSessionDetail,
  DebateSessionSummary,
  ExaminationResponse,
  Stock,
  StockBundle,
} from "./src/types";

type Screen = "watchlist" | "stock" | "debate" | "evidence" | "examine" | "history" | "about";
type DebateExperience = "legacy" | "v2";
type ActiveDebateRecovery = { session: DebateSessionSummary | null };

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
  const { width } = useWindowDimensions();
  const responsiveShell = getResponsiveAppShellLayout(width);
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
  const [reviewFixtureMode, setReviewFixtureMode] = useState(false);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [examination, setExamination] = useState<ExaminationResponse | null>(null);
  const [examinationError, setExaminationError] = useState("");
  const [pendingExaminationQuestion, setPendingExaminationQuestion] = useState<ExaminationResponse["question_type"] | null>(null);
  const [history, setHistory] = useState<AnalysisResponse[]>([]);
  const [debateHistory, setDebateHistory] = useState<DebateSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [debateStarting, setDebateStarting] = useState(false);
  const [activeDebateRecovery, setActiveDebateRecovery] = useState<ActiveDebateRecovery | null>(null);
  const [error, setError] = useState("");
  const debateAdmissionKey = useRef<string | null>(null);
  const debateStartInFlight = useRef(false);
  const stockLoadEpoch = useRef(0);

  const loadHome = async () => {
    try {
      setError("");
      // Older or partially deployed APIs may not expose the optional runtime
      // metadata yet. Preserve the existing stock flow in that case.
      const healthRequest = api.getHealth().catch(() => ({
        data_mode: undefined,
        debate_workflow_v2: undefined,
      }));
      const stockRequest = api.listStocks();
      const watchlistRequest = api.getWatchlist();
      const analysisRequest = api.listAnalyses();
      const health = await healthRequest;
      const fixtureMode = health.data_mode === "review_fixture";
      const fixtureV2 = fixtureMode && health.debate_workflow_v2 === true;
      setReviewFixtureMode(fixtureMode);
      const debateV2Enabled = DEBATE_V2_UI_ENABLED || fixtureV2;
      const [stockResult, watchlistResult, analysisResult, debateResult] = await Promise.all([
        stockRequest,
        watchlistRequest,
        analysisRequest,
        debateV2Enabled
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

  const debateV2Enabled = DEBATE_V2_UI_ENABLED || reviewFixtureMode;

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
    setActiveDebateRecovery(null);
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
    if (debateStartInFlight.current) return;
    debateStartInFlight.current = true;
    const startingV2 = debateV2Enabled;
    setDebateStarting(startingV2);
    if (!startingV2) setLoading(true);
    setActiveDebateRecovery(null);
    setError("");
    try {
      if (startingV2) {
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
      if (startingV2 && isActiveDebateConflict(requestError)) {
        const knownSessions = [
          ...(liveDebate ? [liveDebate.session] : []),
          ...debateHistory,
        ];
        debateAdmissionKey.current = null;
        setActiveDebateRecovery({ session: findActiveDebate(knownSessions) });
      } else {
        setError(requestError instanceof Error ? requestError.message : "Could not run the analysis.");
      }
    } finally {
      debateStartInFlight.current = false;
      setDebateStarting(false);
      if (!startingV2) setLoading(false);
    }
  };

  const openExamination = (claim: Claim) => {
    setSelectedClaim(claim);
    setExamination(null);
    setExaminationError("");
    setPendingExaminationQuestion(null);
    setScreen("examine");
  };

  const askQuestion = async (questionType: ExaminationResponse["question_type"]) => {
    if (!selectedClaim || !canSubmitExamination(pendingExaminationQuestion)) return;
    setPendingExaminationQuestion(questionType);
    setExaminationError("");
    try {
      setExamination(await api.examineClaim(selectedClaim.id, questionType));
    } catch (requestError) {
      setExaminationError(requestError instanceof Error ? requestError.message : "Could not examine the claim.");
    } finally {
      setPendingExaminationQuestion(null);
    }
  };

  const refreshDebateHistory = async () => {
    if (!debateV2Enabled) {
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
    setActiveDebateRecovery(null);
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
      const recoverableDebate = activeDebateRecovery?.session ?? null;
      return (
        <StockDetailScreen
          stock={selectedStock}
          bundle={selectedBundle}
          loading={loading}
          error={error}
          debateStarting={debateStarting}
          activeDebate={recoverableDebate}
          onBack={() => { setError(""); setScreen("watchlist"); }}
          onRetry={() => void openStock(selectedTicker)}
          onEvidence={() => setScreen("evidence")}
          onDebate={startDebate}
          onOpenActiveDebate={recoverableDebate
            ? () => void openSavedDebate(recoverableDebate)
            : undefined}
          onOpenDebateHistory={() => {
            setScreen("history");
            void refreshDebateHistory();
          }}
          showActiveDebateRecovery={activeDebateRecovery !== null}
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
        <LegacyDebateScreen
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
          error={error}
          loading={loading}
          onBack={() => setScreen(analysis ? "debate" : "stock")}
          onRetry={() => void openStock(selectedTicker)}
        />
      );
    }
    if (screen === "examine") {
      return (
        <ExaminationScreen
          claim={selectedClaim}
          error={examinationError}
          pendingQuestion={pendingExaminationQuestion}
          result={examination}
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
      <StatusBar backgroundColor={palette.paper} style="light" />
      <View style={styles.appShell}>
        {reviewFixtureMode ? (
          <View accessibilityRole="text" style={styles.fixtureBanner}>
            <Text style={styles.fixtureBannerText}>SIMULATED DATA · LOCAL UI REVIEW · NOT A MARKET PRICE</Text>
          </View>
        ) : null}
        {error && screen !== "watchlist" && !(screen === "stock" && !selectedBundle) ? (
          <FocusablePressable
            accessibilityHint="Dismisses this error message."
            accessibilityLabel={`Dismiss error: ${error}`}
            accessibilityLiveRegion="assertive"
            accessibilityRole="button"
            style={styles.errorBanner}
            onPress={() => setError("")}
          >
            <Text style={styles.errorText}>{error}</Text>
          </FocusablePressable>
        ) : null}
        <View style={[styles.contentFrame, { maxWidth: responsiveShell.contentMaxWidth }]}>
          {renderScreen()}
        </View>
        <View accessibilityLabel="Primary navigation" accessibilityRole="tablist" style={styles.bottomNav}>
          <View style={[
            styles.bottomNavContent,
            {
              columnGap: responsiveShell.navigationGap,
              maxWidth: responsiveShell.navigationMaxWidth,
              paddingHorizontal: responsiveShell.navigationPadding,
            },
          ]}>
            <NavButton label="Watchlist" active={screen === "watchlist"} onPress={() => nav("watchlist")} />
            <NavButton label="Signals" active={screen === "stock" || screen === "debate" || screen === "evidence" || screen === "examine"} onPress={() => void openStock(selectedTicker)} />
            <NavButton label="History" active={screen === "history"} onPress={() => nav("history")} />
            <NavButton label="About" active={screen === "about"} onPress={() => nav("about")} />
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}
