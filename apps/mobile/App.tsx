import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Text, useWindowDimensions, View } from "react-native";
import {
  initialWindowMetrics,
  SafeAreaProvider,
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { useAnalysisHistory } from "./src/hooks/useAnalysisHistory";
import { useWorkspaceAuth } from "./src/hooks/useWorkspaceAuth";
import { loadWorkspaceHome, mergeStocks } from "./src/workspaceData";

import { api } from "./src/api";
import { getBottomNavigationOffset, getResponsiveAppShellLayout } from "./src/appShell";
import { AuthScreen } from "./src/AuthScreen";
import { FocusablePressable, NavButton } from "./src/components/common";
import { findActiveDebate, isActiveDebateConflict } from "./src/debateHistoryView";
import { useClaimExamination } from "./src/hooks/useClaimExamination";
import { useWatchlistActions } from "./src/hooks/useWatchlistActions";
import { AboutScreen } from "./src/screens/AboutScreen";
import { EvidenceScreen } from "./src/screens/EvidenceScreen";
import { ExaminationScreen } from "./src/screens/ExaminationScreen";
import { HistoryScreen } from "./src/screens/HistoryScreen";
import { LegacyDebateScreen } from "./src/screens/LegacyDebateScreen";
import { LiveDebateScreen } from "./src/screens/LiveDebateScreen";
import { StockDetailScreen } from "./src/screens/StockDetailScreen";
import { WatchlistScreen } from "./src/screens/WatchlistScreen";
import { loadStockDetail } from "./src/stockDetail";
import { isSupabaseConfigured, supabase } from "./src/supabase";
import { palette, appStyles as styles } from "./src/theme";
import type {
  AnalysisResponse,
  Claim,
  DebateSessionDetail,
  DebateSessionSummary,
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

export default function App() {
  return (
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
      <AppContent />
    </SafeAreaProvider>
  );
}

function AppContent() {
  const { width } = useWindowDimensions();
  const { bottom: bottomSafeAreaInset } = useSafeAreaInsets();
  const responsiveShell = getResponsiveAppShellLayout(width);
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [screen, setScreenState] = useState<Screen>("watchlist");
  const navigationEpoch = useRef(0);
  const setScreen = useCallback((next: Screen) => {
    // Returning to the same screen is still a new visit. A pending request
    // from the old visit must not navigate or show an error in the new one.
    navigationEpoch.current += 1;
    setScreenState(next);
  }, []);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [selectedBundle, setSelectedBundle] = useState<StockBundle | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [liveDebate, setLiveDebate] = useState<DebateSessionDetail | null>(null);
  const [debateExperience, setDebateExperience] = useState<DebateExperience>("legacy");
  const [reviewFixtureMode, setReviewFixtureMode] = useState(false);
  const {
    claim: selectedClaim,
    result: examination,
    error: examinationError,
    pendingQuestion: pendingExaminationQuestion,
    open: selectExamination,
    reset: resetExamination,
    ask: askQuestion,
  } = useClaimExamination(api.examineClaim);
  const {
    history,
    setHistory,
    replace: replaceHistory,
    reset: resetHistory,
    hasMore: historyHasMore,
    loading: historyLoading,
    error: historyPageError,
    loadMore: loadMoreHistory,
  } = useAnalysisHistory(api.getAnalysisPage);
  const [debateHistory, setDebateHistory] = useState<DebateSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [debateStarting, setDebateStarting] = useState(false);
  const [activeDebateRecovery, setActiveDebateRecovery] = useState<ActiveDebateRecovery | null>(
    null,
  );
  const [error, setError] = useState("");
  const debateAdmissionKey = useRef<string | null>(null);
  const debateStartInFlight = useRef(false);
  const stockLoadEpoch = useRef(0);
  const accountEpoch = useRef(0);
  const homeLoadEpoch = useRef(0);

  const resetAccountWorkspace = useCallback(() => {
    accountEpoch.current += 1;
    homeLoadEpoch.current += 1;
    stockLoadEpoch.current += 1;
    debateAdmissionKey.current = null;
    debateStartInFlight.current = false;
    setWorkspaceReady(false);
    setScreen("watchlist");
    setStocks([]);
    setWatchlist([]);
    setSelectedTicker("AAPL");
    setSelectedStock(null);
    setSelectedBundle(null);
    setAnalysis(null);
    setLiveDebate(null);
    setDebateExperience("legacy");
    setReviewFixtureMode(false);
    resetExamination();
    resetHistory();
    setDebateHistory([]);
    setLoading(false);
    setDebateStarting(false);
    setActiveDebateRecovery(null);
    setError("");
  }, [resetExamination, resetHistory, setScreen]);

  const { authReady, session } = useWorkspaceAuth(resetAccountWorkspace);

  const loadHome = async () => {
    const requestAccountEpoch = accountEpoch.current;
    const requestHomeEpoch = ++homeLoadEpoch.current;
    const isCurrent = () =>
      accountEpoch.current === requestAccountEpoch && homeLoadEpoch.current === requestHomeEpoch;
    try {
      setError("");
      const home = await loadWorkspaceHome(api, DEBATE_V2_UI_ENABLED);
      if (!isCurrent()) return;
      setReviewFixtureMode(home.reviewFixtureMode);
      setStocks(home.stocks);
      setWatchlist(home.watchlist);
      replaceHistory({ items: home.analyses, next_offset: home.analysisNextOffset });
      setDebateHistory(home.debates);
    } catch (requestError) {
      if (isCurrent())
        setError(requestError instanceof Error ? requestError.message : "Could not load the API.");
    } finally {
      if (isCurrent()) setWorkspaceReady(true);
    }
  };

  const debateV2Enabled = DEBATE_V2_UI_ENABLED || reviewFixtureMode;

  useEffect(() => {
    if (authReady && (!isSupabaseConfigured || session)) {
      void loadHome();
    }
  }, [authReady, session?.access_token]);

  const searchStocks = useCallback(async (query: string): Promise<Stock[]> => {
    const requestAccountEpoch = accountEpoch.current;
    const results = await api.listStocks(query, 20);
    if (accountEpoch.current === requestAccountEpoch) {
      setStocks((current) => mergeStocks(current, results));
    }
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
        setError(
          requestError instanceof Error ? requestError.message : "Could not load stock details.",
        );
      }
    } finally {
      if (stockLoadEpoch.current === requestEpoch) {
        setLoading(false);
      }
    }
  };

  const openStock = async (ticker: string) => {
    // A research visit owns the current stock bundle. Saved analysis evidence
    // stays in History and must not leak into another security's research.
    setAnalysis(null);
    setLiveDebate(null);
    resetExamination();
    setScreen("stock");
    await loadSelectedStock(ticker);
  };

  const toggleWatchlist = useWatchlistActions({ watchlist, setWatchlist, setError, accountEpoch });
  const savedDebateRequest = useRef(0);

  const startDebate = async () => {
    if (selectedStock && selectedStock.coverage_status !== "debate_ready") {
      setError("Bull vs Bear is available only for Debate-ready stocks.");
      return;
    }
    if (debateStartInFlight.current) return;
    const requestAccountEpoch = accountEpoch.current;
    debateStartInFlight.current = true;
    const requestStockEpoch = stockLoadEpoch.current;
    const requestNavigationEpoch = navigationEpoch.current;
    const isCurrentStock = () =>
      accountEpoch.current === requestAccountEpoch &&
      stockLoadEpoch.current === requestStockEpoch &&
      navigationEpoch.current === requestNavigationEpoch;
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
        if (!isCurrentStock()) return;
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
      if (!isCurrentStock()) return;
      setAnalysis(nextAnalysis);
      setDebateExperience("legacy");
      setHistory((current) => [
        nextAnalysis,
        ...current.filter((item) => item.analysis_id !== nextAnalysis.analysis_id),
      ]);
      setScreen("debate");
    } catch (requestError) {
      if (!isCurrentStock()) return;
      if (startingV2 && isActiveDebateConflict(requestError)) {
        const knownSessions = [...(liveDebate ? [liveDebate.session] : []), ...debateHistory];
        debateAdmissionKey.current = null;
        setActiveDebateRecovery({ session: findActiveDebate(knownSessions) });
      } else {
        setError(
          requestError instanceof Error ? requestError.message : "Could not run the analysis.",
        );
      }
    } finally {
      if (accountEpoch.current === requestAccountEpoch) {
        debateStartInFlight.current = false;
        setDebateStarting(false);
        if (!startingV2 && stockLoadEpoch.current === requestStockEpoch) setLoading(false);
      }
    }
  };

  const openExamination = (claim: Claim) => {
    selectExamination(claim);
    setScreen("examine");
  };

  const refreshDebateHistory = async () => {
    const requestAccountEpoch = accountEpoch.current;
    if (!debateV2Enabled) {
      setDebateHistory([]);
      return;
    }
    try {
      const nextHistory = await api.listDebates();
      if (accountEpoch.current === requestAccountEpoch) setDebateHistory(nextHistory);
    } catch {
      // Preserve already loaded canonical history if the optional V2 route is unavailable.
    }
  };

  const openSavedDebate = async (sessionSummary: DebateSessionSummary) => {
    const requestAccountEpoch = accountEpoch.current;
    const requestId = ++savedDebateRequest.current;
    const requestNavigationEpoch = navigationEpoch.current;
    const isCurrent = () =>
      accountEpoch.current === requestAccountEpoch &&
      savedDebateRequest.current === requestId &&
      navigationEpoch.current === requestNavigationEpoch;
    let stockLoadStarted = false;
    setActiveDebateRecovery(null);
    setLoading(true);
    setError("");
    try {
      const detail = await api.getDebate(sessionSummary.id);
      if (!isCurrent()) return;
      setLiveDebate(detail);
      setDebateExperience("v2");
      setScreen("debate");
      stockLoadStarted = true;
      await loadSelectedStock(detail.session.ticker);
    } catch (requestError) {
      if (isCurrent()) {
        setError(
          requestError instanceof Error ? requestError.message : "Could not load this Debate.",
        );
      }
    } finally {
      if (isCurrent() && !stockLoadStarted) setLoading(false);
    }
  };

  const openSavedAnalysis = (item: AnalysisResponse) => {
    // Invalidate a pending V2 history request before opening a classic result.
    savedDebateRequest.current += 1;
    setAnalysis(item);
    setLiveDebate(null);
    resetExamination();
    setDebateExperience("legacy");
    setScreen("debate");
    // The frozen analysis remains visible while its own research page loads.
    // Returning to research must never show the previously visited stock.
    void loadSelectedStock(item.ticker);
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
          onBack={() => {
            setError("");
            setScreen("watchlist");
          }}
          onRetry={() => void openStock(selectedTicker)}
          onEvidence={() => setScreen("evidence")}
          onDebate={startDebate}
          onOpenActiveDebate={
            recoverableDebate ? () => void openSavedDebate(recoverableDebate) : undefined
          }
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
            key={`${session?.user.id || "demo"}:${liveDebate.session.id}`}
            accountId={session?.user.id || "demo"}
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
          evidence={selectedBundle?.evidence || []}
          error={error}
          loading={loading}
          onBack={() => setScreen("stock")}
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
          onBack={() => {
            resetExamination();
            setScreen("debate");
          }}
          onAsk={askQuestion}
        />
      );
    }
    if (screen === "history") {
      return (
        <HistoryScreen
          history={history}
          hasMore={historyHasMore}
          loadingMore={historyLoading}
          pageError={historyPageError}
          onLoadMore={() => void loadMoreHistory()}
          debates={debateHistory}
          onOpen={openSavedAnalysis}
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
        <View style={styles.loading}>
          <ActivityIndicator color={palette.accent} size="large" />
        </View>
      </SafeAreaView>
    );
  }
  if (isSupabaseConfigured && !session) {
    return <AuthScreen />;
  }
  if (!workspaceReady) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loading}>
          <ActivityIndicator color={palette.accent} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.appShell}>
        {reviewFixtureMode ? (
          <View accessibilityRole="text" style={styles.fixtureBanner}>
            <Text style={styles.fixtureBannerText}>
              SIMULATED DATA · LOCAL UI REVIEW · NOT A MARKET PRICE
            </Text>
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
        <View
          accessibilityLabel="Primary navigation"
          accessibilityRole="tablist"
          style={[styles.bottomNav, { bottom: getBottomNavigationOffset(bottomSafeAreaInset) }]}
        >
          <View
            style={[
              styles.bottomNavContent,
              {
                columnGap: responsiveShell.navigationGap,
                maxWidth: responsiveShell.navigationMaxWidth,
                paddingHorizontal: responsiveShell.navigationPadding,
              },
            ]}
          >
            <NavButton
              label="Watchlist"
              active={screen === "watchlist"}
              onPress={() => nav("watchlist")}
            />
            <NavButton
              label="Signals"
              active={
                screen === "stock" ||
                screen === "debate" ||
                screen === "evidence" ||
                screen === "examine"
              }
              onPress={() => void openStock(selectedTicker)}
            />
            <NavButton
              label="History"
              active={screen === "history"}
              onPress={() => nav("history")}
            />
            <NavButton label="About" active={screen === "about"} onPress={() => nav("about")} />
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}
