import { useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";

import { FocusablePressable, SectionHeader } from "../components/common";
import { getCoveragePresentation } from "../discoverySummary";
import { colors, interaction, layout, palette, radii, spacing } from "../theme";
import type { Stock } from "../types";

type WatchlistScreenProps = {
  stocks: Stock[];
  watchlist: string[];
  error: string;
  onOpen: (ticker: string) => void;
  onToggle: (ticker: string) => void;
  onRetry: () => void;
  onSearch: (query: string) => Promise<Stock[]>;
};

export function WatchlistScreen({
  stocks,
  watchlist,
  error,
  onOpen,
  onToggle,
  onRetry,
  onSearch,
}: WatchlistScreenProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Stock[]>(
    stocks.filter((stock) => stock.coverage_status === "debate_ready"),
  );
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const visible = useMemo(
    () => stocks.filter((stock) => watchlist.includes(stock.ticker)),
    [stocks, watchlist],
  );
  const catalogResults = useMemo(
    () => query.trim() ? results : results.filter((stock) => !watchlist.includes(stock.ticker)),
    [query, results, watchlist],
  );
  const { width: viewportWidth } = useWindowDimensions();
  const isWideLayout = viewportWidth >= layout.breakpoints.tablet;

  useEffect(() => {
    if (!query.trim()) {
      setResults(stocks.filter((stock) => stock.coverage_status === "debate_ready"));
      setSearchError("");
      setSearching(false);
    }
  }, [query, stocks]);

  useEffect(() => {
    const normalized = query.trim();
    if (!normalized) return;
    let active = true;
    setSearching(true);
    const timeout = setTimeout(() => {
      void onSearch(normalized)
        .then((next) => {
          if (active) {
            setResults(next);
            setSearchError("");
          }
        })
        .catch((requestError: unknown) => {
          if (active) {
            setResults([]);
            setSearchError(requestError instanceof Error ? requestError.message : "Catalog search failed.");
          }
        })
        .finally(() => {
          if (active) setSearching(false);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [onSearch, query]);

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={styles.hero}>
        <Text accessibilityRole="header" style={styles.title}>Watchlist</Text>
        <Text style={styles.heroCount}>{visible.length} saved</Text>
      </View>
      {error ? (
        <View accessibilityLiveRegion="assertive" style={styles.errorCard}>
          <Text style={styles.errorTitle}>Workspace data could not refresh</Text>
          <Text style={styles.errorText}>{error}</Text>
          <FocusablePressable accessibilityRole="button" onPress={onRetry} style={styles.retryButton}><Text style={styles.retryText}>Retry</Text></FocusablePressable>
        </View>
      ) : null}
      <View style={[styles.workspaceGrid, isWideLayout && styles.workspaceGridWide]}>
        <View style={[styles.watchlistPanel, isWideLayout && styles.watchlistPanelWide]}>
          <SectionHeader title="Saved stocks" />
          {visible.length ? visible.map((stock) => (
            <StockRow key={stock.ticker} stock={stock} watched onOpen={onOpen} onToggle={onToggle} />
          )) : (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>No saved stocks yet</Text>
              <Text style={styles.emptyText}>Tap ☆ to add one.</Text>
            </View>
          )}
        </View>
        <View style={[styles.catalogPanel, isWideLayout && styles.catalogPanelWide]}>
          <View style={[styles.catalogHeading, isWideLayout && styles.catalogHeadingWide]}>
            <Text style={styles.catalogTitle}>Find stocks</Text>
          </View>
          <TextInput
            accessibilityLabel="Search ticker or company"
            autoCapitalize="characters"
            onChangeText={setQuery}
            placeholder="Search ticker or company"
            placeholderTextColor={palette.muted}
            style={styles.search}
            value={query}
          />
          {searching ? <Text accessibilityLiveRegion="polite" style={styles.searchStatus}>Searching…</Text> : null}
          {searchError ? <Text accessibilityLiveRegion="assertive" style={styles.searchError}>{searchError}</Text> : null}
          {!searching && !searchError && query.trim() && catalogResults.length === 0 ? (
            <View style={styles.emptyCard}><Text style={styles.emptyTitle}>No matching stocks</Text><Text style={styles.emptyText}>Try another ticker or company.</Text></View>
          ) : null}
          {!searching && catalogResults.map((stock) => (
            <StockRow key={stock.ticker} stock={stock} watched={watchlist.includes(stock.ticker)} onOpen={onOpen} onToggle={onToggle} />
          ))}
        </View>
      </View>
      <View style={styles.disclaimerBox}>
        <Text style={styles.disclaimerText}>For research only. Not a recommendation to buy, sell, or hold.</Text>
      </View>
    </ScrollView>
  );
}

function StockRow({ stock, watched, onOpen, onToggle }: {
  stock: Stock;
  watched: boolean;
  onOpen: (ticker: string) => void;
  onToggle: (ticker: string) => void;
}) {
  const coverage = getCoveragePresentation(stock.coverage_status);
  const isCatalogOnly = coverage.tone === "catalog";
  const shortCoverageLabel = stock.coverage_status === "debate_ready" ? "Ready"
    : stock.coverage_status === "evidence_ready" ? "Evidence"
      : stock.coverage_status === "price_cached" ? "Limited" : "Watchlist only";
  return (
    <View style={styles.stockRow}>
      <FocusablePressable
        accessibilityHint={isCatalogOnly ? "Opens this security's catalog details." : "Opens this security's research workspace."}
        accessibilityLabel={`${stock.ticker}, ${stock.company_name}, ${coverage.label}`}
        accessibilityRole="button"
        onPress={() => onOpen(stock.ticker)}
        style={styles.stockMain}
      >
        <View style={[styles.symbolBadge, isCatalogOnly && styles.catalogBadge]}><Text style={[styles.symbolText, isCatalogOnly && styles.catalogSymbolText]}>{stock.ticker.slice(0, 1)}</Text></View>
        <View style={styles.stockCopy}>
          <View style={styles.tickerRow}>
            <Text style={styles.stockTicker}>{stock.ticker}</Text>
            <Text style={[
              styles.coverageBadge,
              coverage.tone === "ready" ? styles.readyBadge : coverage.tone === "partial" ? styles.partialBadge : styles.catalogOnlyBadge,
            ]}>{shortCoverageLabel}</Text>
          </View>
          <Text numberOfLines={1} style={styles.stockCompany}>{stock.company_name}</Text>
        </View>
      </FocusablePressable>
      <FocusablePressable
        accessibilityLabel={watched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
        accessibilityRole="button"
        accessibilityState={{ selected: watched }}
        onPress={() => onToggle(stock.ticker)}
        style={styles.starButton}
      >
        <Text style={[styles.star, watched && styles.starActive]}>{watched ? "★" : "☆"}</Text>
      </FocusablePressable>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { alignSelf: "center", maxWidth: layout.contentMaxWidth, padding: spacing.xl, paddingBottom: 110, width: "100%" },
  hero: { backgroundColor: colors.surface.elevated, borderColor: palette.line, borderRadius: radii.xl, borderWidth: 1, marginBottom: spacing.lg, padding: spacing.xl },
  title: { color: palette.ink, fontSize: 31, fontWeight: "800", lineHeight: 37 },
  heroCount: { color: palette.muted, fontSize: 13, marginTop: spacing.xs },
  errorCard: { backgroundColor: colors.surface.danger, borderRadius: radii.md, marginBottom: spacing.md, padding: spacing.md },
  errorTitle: { color: colors.content.danger, fontSize: 14, fontWeight: "800", marginBottom: 2 },
  errorText: { color: colors.content.danger, fontSize: 12, lineHeight: 18 },
  retryButton: { alignSelf: "flex-start", backgroundColor: palette.signal, borderRadius: radii.sm, marginTop: spacing.sm, minHeight: interaction.minTargetSize, justifyContent: "center", paddingHorizontal: spacing.md },
  retryText: { color: colors.content.onSignal, fontSize: 13, fontWeight: "800" },
  emptyCard: { backgroundColor: colors.surface.subtle, borderColor: palette.line, borderRadius: radii.md, borderStyle: "dashed", borderWidth: 1, padding: spacing.lg },
  emptyTitle: { color: palette.ink, fontSize: 15, fontWeight: "800", marginBottom: spacing.xs },
  emptyText: { color: palette.muted, fontSize: 13, lineHeight: 20 },
  workspaceGrid: { minWidth: 0 },
  workspaceGridWide: { alignItems: "flex-start", flexDirection: "row", gap: spacing.xl },
  watchlistPanel: { minWidth: 0 },
  watchlistPanelWide: { flex: 1, minWidth: 0 },
  catalogPanel: { minWidth: 0 },
  catalogPanelWide: { flex: 1, minWidth: 0 },
  catalogHeading: { marginTop: spacing.xxl },
  catalogHeadingWide: { marginTop: 18 },
  catalogTitle: { color: palette.ink, fontSize: 23, fontWeight: "800", lineHeight: 29, marginBottom: spacing.md },
  search: { backgroundColor: palette.card, borderColor: palette.line, borderRadius: radii.md, borderWidth: 1, color: palette.ink, fontSize: 16, minHeight: interaction.minTargetSize, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  searchStatus: { color: palette.muted, fontSize: 12, marginTop: spacing.sm },
  searchError: { color: colors.content.danger, fontSize: 12, lineHeight: 18, marginTop: spacing.sm },
  stockRow: { alignItems: "center", backgroundColor: palette.card, borderColor: palette.line, borderRadius: radii.lg, borderWidth: 1, flexDirection: "row", marginBottom: spacing.sm, minHeight: 72, padding: spacing.sm },
  stockMain: { alignItems: "center", flex: 1, flexDirection: "row", minHeight: interaction.minTargetSize },
  symbolBadge: { alignItems: "center", backgroundColor: palette.accent, borderRadius: radii.md, height: interaction.minTargetSize, justifyContent: "center", width: interaction.minTargetSize },
  catalogBadge: { backgroundColor: colors.surface.information },
  symbolText: { color: colors.content.inverse, fontSize: 18, fontWeight: "800" },
  catalogSymbolText: { color: palette.accent },
  stockCopy: { flex: 1, marginLeft: spacing.md, minWidth: 0 },
  tickerRow: { alignItems: "center", flexDirection: "row", flexWrap: "wrap", columnGap: spacing.sm, rowGap: spacing.xs, minWidth: 0 },
  stockTicker: { color: palette.ink, fontSize: 16, fontWeight: "900", flexShrink: 1 },
  coverageBadge: { borderRadius: radii.sm, fontSize: 10, fontWeight: "800", overflow: "hidden", paddingHorizontal: spacing.sm, paddingVertical: 3 },
  readyBadge: { backgroundColor: colors.surface.positive, color: palette.accent },
  partialBadge: { backgroundColor: colors.surface.warning, color: colors.content.warning },
  catalogOnlyBadge: { backgroundColor: colors.surface.information, color: palette.accent },
  stockCompany: { color: palette.muted, fontSize: 13, marginTop: 2 },
  starButton: { alignItems: "center", justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize },
  star: { color: palette.muted, fontSize: 26, fontWeight: "800" },
  starActive: { color: palette.accent },
  disclaimerBox: { backgroundColor: colors.surface.subtle, borderRadius: radii.md, marginTop: spacing.xl, padding: spacing.lg },
  disclaimerText: { color: palette.ink, fontSize: 12, lineHeight: 18 },
});
