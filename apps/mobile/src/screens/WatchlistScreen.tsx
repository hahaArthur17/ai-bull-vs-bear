import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { SectionHeader } from "../components/common";
import { getDiscoverySummary } from "../discoverySummary";
import { colors, interaction, palette, radii, spacing, typography } from "../theme";
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
  const { readyToReview } = useMemo(() => getDiscoverySummary(stocks), [stocks]);

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
        <Text style={styles.eyebrow}>RESEARCH QUEUE</Text>
        <Text accessibilityRole="header" style={styles.title}>Track the names worth revisiting.</Text>
        <Text style={styles.heroBody}>Search the versioned security catalog, keep a focused watchlist, then open available research context.</Text>
        <View style={styles.statRow}>
          <View style={styles.stat}><Text style={styles.statValue}>{visible.length}</Text><Text style={styles.statLabel}>WATCHED</Text></View>
          <View style={styles.statDivider} />
          <View style={styles.stat}><Text style={styles.statValue}>{readyToReview}</Text><Text style={styles.statLabel}>READY TO REVIEW</Text></View>
        </View>
      </View>
      {error ? (
        <View accessibilityLiveRegion="assertive" style={styles.errorCard}>
          <Text style={styles.errorTitle}>Workspace data could not refresh</Text>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable accessibilityRole="button" onPress={onRetry} style={styles.retryButton}><Text style={styles.retryText}>Retry</Text></Pressable>
        </View>
      ) : null}
      <SectionHeader title="Your watchlist" meta={`${visible.length} saved`} />
      {visible.length ? visible.map((stock) => (
        <StockRow key={stock.ticker} stock={stock} watched onOpen={onOpen} onToggle={onToggle} />
      )) : (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>Your watchlist is clear.</Text>
          <Text style={styles.emptyText}>Save a catalog symbol to keep it at the top of this research queue.</Text>
        </View>
      )}
      <View style={styles.catalogHeading}>
        <Text style={styles.eyebrow}>SECURITY CATALOG</Text>
        <Text style={styles.catalogTitle}>Find a listed security</Text>
        <Text style={styles.catalogBody}>Catalog search identifies securities only. A coverage label tells you whether research data is available before opening it.</Text>
      </View>
      <Text style={styles.label}>TICKER OR COMPANY</Text>
      <TextInput
        accessibilityLabel="Search ticker or company"
        autoCapitalize="characters"
        onChangeText={setQuery}
        placeholder="For example: AAPL or Apple"
        placeholderTextColor={palette.muted}
        style={styles.search}
        value={query}
      />
      {searching ? <Text accessibilityLiveRegion="polite" style={styles.searchStatus}>Searching the security catalog…</Text> : null}
      {searchError ? <Text accessibilityLiveRegion="assertive" style={styles.searchError}>{searchError}</Text> : null}
      {!searching && !searchError && results.length === 0 ? (
        <View style={styles.emptyCard}><Text style={styles.emptyTitle}>No matching symbol</Text><Text style={styles.emptyText}>Try a ticker, a shorter company name, or clear the query to browse available research coverage.</Text></View>
      ) : null}
      {results.map((stock) => (
        <StockRow key={stock.ticker} stock={stock} watched={watchlist.includes(stock.ticker)} onOpen={onOpen} onToggle={onToggle} />
      ))}
      <View style={styles.disclaimerBox}>
        <Text style={styles.disclaimerText}>Educational research context only. Nothing here is a recommendation to buy, sell, or hold a security.</Text>
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
  const isReady = stock.coverage_status === "debate_ready";
  const coverageLabel = isReady ? "Research ready" : "Watchlist only";
  return (
    <View style={styles.stockRow}>
      <Pressable
        accessibilityHint="Opens this security's research workspace."
        accessibilityLabel={`${stock.ticker}, ${stock.company_name}, ${coverageLabel}`}
        accessibilityRole="button"
        onPress={() => onOpen(stock.ticker)}
        style={styles.stockMain}
      >
        <View style={[styles.symbolBadge, !isReady && styles.catalogBadge]}><Text style={[styles.symbolText, !isReady && styles.catalogSymbolText]}>{stock.ticker.slice(0, 1)}</Text></View>
        <View style={styles.stockCopy}>
          <View style={styles.tickerRow}><Text style={styles.stockTicker}>{stock.ticker}</Text><Text style={[styles.coverageBadge, isReady ? styles.readyBadge : styles.catalogOnlyBadge]}>{coverageLabel}</Text></View>
          <Text numberOfLines={1} style={styles.stockCompany}>{stock.company_name}</Text>
          <Text style={styles.stockMeta}>{stock.exchange}{stock.sector ? ` · ${stock.sector}` : ""}</Text>
        </View>
      </Pressable>
      <Pressable
        accessibilityLabel={watched ? `Remove ${stock.ticker} from watchlist` : `Add ${stock.ticker} to watchlist`}
        accessibilityRole="button"
        accessibilityState={{ selected: watched }}
        onPress={() => onToggle(stock.ticker)}
        style={styles.starButton}
      >
        <Text style={[styles.star, watched && styles.starActive]}>{watched ? "★" : "☆"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.xl, paddingBottom: 110 },
  hero: { backgroundColor: palette.accent, borderRadius: radii.xl, marginBottom: spacing.lg, padding: spacing.xl },
  eyebrow: { color: colors.content.inverseSubtle, fontSize: typography.label.fontSize, fontWeight: typography.label.fontWeight, letterSpacing: typography.label.letterSpacing, marginBottom: spacing.xs },
  title: { color: colors.content.inverse, fontSize: 31, fontWeight: "800", lineHeight: 37 },
  heroBody: { color: colors.content.inverseMuted, fontSize: 15, lineHeight: 22, marginTop: spacing.sm },
  statRow: { alignItems: "center", flexDirection: "row", marginTop: spacing.lg },
  stat: { flex: 1 },
  statValue: { color: colors.content.inverse, fontSize: 21, fontWeight: "900" },
  statLabel: { color: colors.content.inverseSubtle, fontSize: 10, fontWeight: "800", letterSpacing: 0.8, marginTop: 2 },
  statDivider: { backgroundColor: colors.border.inverse, height: 32, width: 1 },
  errorCard: { backgroundColor: colors.surface.danger, borderRadius: radii.md, marginBottom: spacing.md, padding: spacing.md },
  errorTitle: { color: colors.content.danger, fontSize: 14, fontWeight: "800", marginBottom: 2 },
  errorText: { color: colors.content.danger, fontSize: 12, lineHeight: 18 },
  retryButton: { alignSelf: "flex-start", backgroundColor: palette.signal, borderRadius: radii.sm, marginTop: spacing.sm, minHeight: interaction.minTargetSize, justifyContent: "center", paddingHorizontal: spacing.md },
  retryText: { color: "#fff", fontSize: 13, fontWeight: "800" },
  emptyCard: { backgroundColor: colors.surface.subtle, borderColor: palette.line, borderRadius: radii.md, borderStyle: "dashed", borderWidth: 1, padding: spacing.lg },
  emptyTitle: { color: palette.ink, fontSize: 15, fontWeight: "800", marginBottom: spacing.xs },
  emptyText: { color: palette.muted, fontSize: 13, lineHeight: 20 },
  catalogHeading: { marginTop: spacing.xxl },
  catalogTitle: { color: palette.ink, fontSize: 23, fontWeight: "800", lineHeight: 29, marginBottom: spacing.xs },
  catalogBody: { color: palette.muted, fontSize: 13, lineHeight: 20, marginBottom: spacing.lg },
  label: { color: palette.ink, fontSize: 11, fontWeight: "800", letterSpacing: 0.8, marginBottom: spacing.xs },
  search: { backgroundColor: palette.card, borderColor: palette.line, borderRadius: radii.md, borderWidth: 1, color: palette.ink, fontSize: 16, minHeight: interaction.minTargetSize, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  searchStatus: { color: palette.muted, fontSize: 12, marginTop: spacing.sm },
  searchError: { color: colors.content.danger, fontSize: 12, lineHeight: 18, marginTop: spacing.sm },
  stockRow: { alignItems: "center", backgroundColor: palette.card, borderColor: palette.line, borderRadius: radii.lg, borderWidth: 1, flexDirection: "row", marginBottom: spacing.sm, minHeight: 72, padding: spacing.sm },
  stockMain: { alignItems: "center", flex: 1, flexDirection: "row", minHeight: interaction.minTargetSize },
  symbolBadge: { alignItems: "center", backgroundColor: palette.accent, borderRadius: radii.md, height: interaction.minTargetSize, justifyContent: "center", width: interaction.minTargetSize },
  catalogBadge: { backgroundColor: colors.surface.information },
  symbolText: { color: "#fff", fontSize: 18, fontWeight: "800" },
  catalogSymbolText: { color: palette.accent },
  stockCopy: { flex: 1, marginLeft: spacing.md, minWidth: 0 },
  tickerRow: { alignItems: "center", flexDirection: "row", gap: spacing.sm },
  stockTicker: { color: palette.ink, fontSize: 16, fontWeight: "900" },
  coverageBadge: { borderRadius: radii.sm, fontSize: 10, fontWeight: "800", overflow: "hidden", paddingHorizontal: spacing.sm, paddingVertical: 3 },
  readyBadge: { backgroundColor: colors.surface.positive, color: palette.bull },
  catalogOnlyBadge: { backgroundColor: colors.surface.information, color: palette.accent },
  stockCompany: { color: palette.muted, fontSize: 13, marginTop: 2 },
  stockMeta: { color: palette.muted, fontSize: 11, marginTop: 2 },
  starButton: { alignItems: "center", justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize },
  star: { color: palette.muted, fontSize: 26 },
  starActive: { color: palette.signal },
  disclaimerBox: { backgroundColor: colors.surface.subtle, borderRadius: radii.md, marginTop: spacing.xl, padding: spacing.lg },
  disclaimerText: { color: palette.ink, fontSize: 12, lineHeight: 18 },
});
