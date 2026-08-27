import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { SectionHeader } from "../components/common";
import { appStyles as styles, palette } from "../theme";
import type { Stock } from "../types";


export function WatchlistScreen({
  stocks,
  watchlist,
  error,
  onOpen,
  onToggle,
  onRetry,
  onSearch,
}: {
  stocks: Stock[];
  watchlist: string[];
  error: string;
  onOpen: (ticker: string) => void;
  onToggle: (ticker: string) => void;
  onRetry: () => void;
  onSearch: (query: string) => Promise<Stock[]>;
}) {
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
            setSearchError(
              requestError instanceof Error ? requestError.message : "Catalog search failed.",
            );
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
      <SectionHeader title="Security catalog" meta="zero market-data calls" />
      <Text style={styles.mutedText}>
        Search exchange-listed securities by ticker or issuer. Catalog results are identities, not a
        promise of price or debate coverage.
      </Text>
      <TextInput
        placeholder="Search ticker or company"
        placeholderTextColor={palette.muted}
        value={query}
        onChangeText={setQuery}
        style={styles.search}
        autoCapitalize="characters"
      />
      {searching ? <Text style={styles.mutedText}>Searching the security catalog…</Text> : null}
      {searchError ? <Text style={styles.errorText}>{searchError}</Text> : null}
      {!searching && !searchError && results.length === 0 ? (
        <Text style={styles.mutedText}>No matching catalog symbol.</Text>
      ) : null}
      {results.map((stock) => (
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
          <Text style={styles.mutedText}>
            {stock.coverage_status === "debate_ready" ? "Debate ready" : "Watchlist only"}
          </Text>
        </View>
      </Pressable>
      <Pressable onPress={() => onToggle(stock.ticker)} style={styles.starButton}>
        <Text style={[styles.star, watched && styles.starActive]}>{watched ? "★" : "☆"}</Text>
      </Pressable>
    </View>
  );
}
