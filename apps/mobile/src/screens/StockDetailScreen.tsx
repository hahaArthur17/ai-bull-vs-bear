import { ScrollView, Text, useWindowDimensions, View } from "react-native";
import { InteractivePriceChart } from "../components/research/InteractivePriceChart";
import { MacroContextPanel, TechnicalPanels } from "../components/research/TechnicalPanels";
import { workspaceStyles } from "../components/research/researchStyles";
import type { ChartRange } from "../research/priceChart";

import {
  BackButton,
  FailureView,
  FocusablePressable,
  LoadingView,
  Metric,
  SectionHeader,
} from "../components/common";
import { formatQuoteTime } from "../dateFormat";
import { getResearchWorkspaceLayout } from "../research/workspaceLayout";
import type { QuoteProvenance } from "../stockResearchSummary";
import { getQuoteProvenance } from "../stockResearchSummary";
import { appStyles as styles } from "../theme";
import type { DebateSessionSummary, Stock, StockBundle, TechnicalIndicators } from "../types";

export function StockDetailScreen({
  stock,
  bundle,
  loading,
  debateStarting,
  activeDebate,
  error,
  onBack,
  onRetry,
  onEvidence,
  onDebate,
  onOpenActiveDebate,
  onOpenDebateHistory,
  showActiveDebateRecovery,
  isWatched,
  onToggleWatchlist,
}: {
  stock: Stock | null;
  bundle: StockBundle | null;
  loading: boolean;
  debateStarting: boolean;
  activeDebate: DebateSessionSummary | null;
  error: string;
  onBack: () => void;
  onRetry: () => void;
  onEvidence: () => void;
  onDebate: () => void;
  onOpenActiveDebate?: () => void;
  onOpenDebateHistory: () => void;
  showActiveDebateRecovery: boolean;
  isWatched: boolean;
  onToggleWatchlist: () => void;
}) {
  const { width: viewportWidth } = useWindowDimensions();
  if (loading) return <LoadingView label="Loading stock detail..." onBack={onBack} />;
  if (stock?.coverage_status === "catalog_only") {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <BackButton onPress={onBack} />
        <StockResearchHeader
          stock={stock}
          isWatched={isWatched}
          onToggleWatchlist={onToggleWatchlist}
        />
        <View style={styles.catalogIdentityCard}>
          <Text style={styles.cardLabel}>CATALOG IDENTITY</Text>
          <Text style={styles.catalogAvailability}>Watchlist available · research unavailable</Text>
          <Text style={styles.mutedText}>
            This identity comes from the versioned SEC catalog. It can be saved to your Watchlist,
            but cached prices, evidence, technical signals, and Bull vs Bear are not configured.
          </Text>
          <Text style={styles.catalogMetadata}>Source · Versioned SEC security catalog</Text>
          <Text style={styles.catalogMetadata}>
            Coverage checked · {formatQuoteTime(stock.coverage_updated_at)}
          </Text>
          {stock.sec_cik ? (
            <Text style={styles.catalogMetadata}>SEC CIK · {stock.sec_cik}</Text>
          ) : null}
        </View>
        <View style={styles.catalogBoundaryCard}>
          <Text style={styles.cardTitle}>Identity-only boundary</Text>
          <Text style={styles.mutedText}>
            Opening this profile did not request market data, news, evidence retrieval, or an AI
            model.
          </Text>
        </View>
        <FocusablePressable
          accessibilityLabel={
            isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`
          }
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
  const { hasPriceCurve, hasVerifiedMarketData, preferredChartRange } = quoteProvenance;
  const availability = bundle.indicators.availability;
  const hasAnyTechnicalData = Boolean(availability && Object.values(availability).some(Boolean));
  const historyExplanation =
    bundle.indicators.history?.explanation ?? "Daily history has not been assessed.";
  const workspaceLayout = getResearchWorkspaceLayout(viewportWidth);
  const isSimulated =
    bundle.data_mode === "review_fixture" ||
    bundle.indicators.history?.provenance === "review_fixture";
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
  const actions = (
    <ResearchActions
      activeDebate={activeDebate}
      debateStarting={debateStarting}
      onDebate={onDebate}
      onEvidence={onEvidence}
      onOpenActiveDebate={onOpenActiveDebate}
      onOpenDebateHistory={onOpenDebateHistory}
      showActiveDebateRecovery={showActiveDebateRecovery}
    />
  );
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <StockResearchHeader
        stock={bundle.stock}
        isWatched={isWatched}
        onToggleWatchlist={onToggleWatchlist}
      />
      <View
        style={[
          workspaceStyles.overview,
          workspaceLayout.overviewColumns === 2 && workspaceStyles.overviewDesktop,
        ]}
      >
        <View style={workspaceStyles.primaryColumn}>
          <PriceResearchCard
            ticker={bundle.stock.ticker}
            quoteProvenance={quoteProvenance}
            hasPriceCurve={hasPriceCurve}
            dailyPrices={bundle.prices}
            weeklyPrices={bundle.weekly_history}
            initialRange={preferredChartRange}
            historyExplanation={historyExplanation}
          />
          {!workspaceLayout.showReadinessSidebar ? snapshot : null}
          <TechnicalPanels
            prices={bundle.prices}
            availability={availability}
            chartColumns={workspaceLayout.chartColumns}
          />
          <MacroContextPanel
            ticker={bundle.stock.ticker}
            context={bundle.macro_context}
            chartColumns={workspaceLayout.chartColumns}
          />
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
  return (
    <View style={styles.researchHeader}>
      <View style={styles.tickerTile}>
        <Text style={styles.tickerTileText}>{stock.ticker.slice(0, 1)}</Text>
      </View>
      <View style={styles.researchHeaderCopy}>
        <Text style={styles.eyebrow}>
          {stock.exchange} · {isCatalogOnly ? "CATALOG IDENTITY" : "STOCK RESEARCH"}
        </Text>
        <Text style={styles.detailTitle}>{stock.company_name}</Text>
        <Text style={styles.detailTicker}>
          {stock.ticker} · {stock.sector || "Classification unavailable"}
        </Text>
        {isCatalogOnly ? (
          <Text style={[styles.coverageStatus, styles.coverageStatusCatalog]}>Watchlist only</Text>
        ) : null}
      </View>
      <FocusablePressable
        accessibilityLabel={
          isWatched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`
        }
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
  hasPriceCurve,
  dailyPrices,
  weeklyPrices,
  initialRange,
  historyExplanation,
}: {
  ticker: string;
  quoteProvenance: QuoteProvenance;
  hasPriceCurve: boolean;
  dailyPrices: StockBundle["prices"];
  weeklyPrices: StockBundle["weekly_history"];
  initialRange: ChartRange;
  historyExplanation: string;
}) {
  return (
    <View style={styles.priceCard}>
      <Text style={styles.cardLabel}>{quoteProvenance.label.toUpperCase()}</Text>
      {quoteProvenance.value !== null ? (
        <Text accessibilityLiveRegion="polite" style={styles.priceValue}>
          {"$"}
          {quoteProvenance.value.toFixed(2)}
        </Text>
      ) : (
        <Text style={styles.unavailablePrice}>—</Text>
      )}
      {quoteProvenance.value !== null ? (
        <Text style={styles.priceMeta}>
          {quoteProvenance.timestamp.replace(/^[^·]+· /, "As of ")}
        </Text>
      ) : null}
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
      <SectionHeader title="Signal snapshot" />
      <View style={workspaceStyles.readinessMeta}>
        <Text style={styles.mutedText}>
          {isSimulated
            ? "Simulated review data · not a market price"
            : hasVerifiedMarketData
              ? "Verified daily data"
              : "Historical data verification pending"}
        </Text>
      </View>
      {hasAnyTechnicalData ? (
        <>
          <View style={styles.metricGrid}>
            <Metric label="RSI" value={availability?.rsi ? indicators.rsi.toFixed(1) : "—"} />
            <Metric label="MACD" value={availability?.macd ? indicators.macd.toFixed(2) : "—"} />
            <Metric
              label="MA20"
              value={
                availability?.moving_average_20 ? indicators.moving_average_20.toFixed(2) : "—"
              }
            />
            <Metric
              label="Volatility"
              value={availability?.volatility ? indicators.volatility.toFixed(1) + "%" : "—"}
            />
          </View>
          <View style={styles.signalCard}>
            <Text style={styles.signalText}>{indicators.signal_summary}</Text>
          </View>
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

function ResearchActions({
  activeDebate,
  debateStarting,
  onDebate,
  onEvidence,
  onOpenActiveDebate,
  onOpenDebateHistory,
  showActiveDebateRecovery,
}: {
  activeDebate: DebateSessionSummary | null;
  debateStarting: boolean;
  onDebate: () => void;
  onEvidence: () => void;
  onOpenActiveDebate?: () => void;
  onOpenDebateHistory: () => void;
  showActiveDebateRecovery: boolean;
}) {
  const debateBlocked = debateStarting || showActiveDebateRecovery;
  return (
    <View style={styles.actionRow}>
      <FocusablePressable
        accessibilityHint="Opens the dated evidence used by the research workflow."
        accessibilityRole="button"
        style={styles.secondaryButton}
        onPress={onEvidence}
      >
        <Text style={styles.secondaryButtonText}>Evidence board</Text>
      </FocusablePressable>
      <FocusablePressable
        accessibilityHint={
          showActiveDebateRecovery
            ? "Open the existing Debate or History before starting another."
            : "Starts Bull vs Bear for this research-ready security."
        }
        accessibilityRole="button"
        accessibilityState={{ busy: debateStarting, disabled: debateBlocked }}
        disabled={debateBlocked}
        style={[styles.primaryButton, debateBlocked && workspaceStyles.disabledAction]}
        onPress={onDebate}
      >
        <Text style={styles.primaryButtonText}>
          {debateStarting
            ? "Starting Debate…"
            : showActiveDebateRecovery
              ? "An unfinished Debate is active"
              : "Start Bull vs Bear →"}
        </Text>
      </FocusablePressable>
      {showActiveDebateRecovery ? (
        <View
          accessibilityLiveRegion="assertive"
          accessibilityRole="alert"
          style={workspaceStyles.debateRecovery}
        >
          <Text style={workspaceStyles.debateRecoveryTitle}>
            You already have an unfinished Debate
          </Text>
          <Text style={workspaceStyles.debateRecoveryText}>
            {activeDebate
              ? `${activeDebate.ticker} is ${activeDebate.status.replaceAll("_", " ")}. Open that session or review your Debate History before starting another.`
              : "Open Debate History to find the active session before starting another."}
          </Text>
          <View style={workspaceStyles.debateRecoveryActions}>
            {activeDebate && onOpenActiveDebate ? (
              <FocusablePressable
                accessibilityLabel={`Open current ${activeDebate.ticker} Debate`}
                accessibilityRole="button"
                style={styles.smallButton}
                onPress={onOpenActiveDebate}
              >
                <Text style={styles.smallButtonText}>Open current Debate</Text>
              </FocusablePressable>
            ) : null}
            <FocusablePressable
              accessibilityLabel="Open Debate History"
              accessibilityRole="button"
              style={workspaceStyles.historyAction}
              onPress={onOpenDebateHistory}
            >
              <Text style={styles.secondaryButtonText}>Go to History</Text>
            </FocusablePressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}
