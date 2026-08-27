import React, { useMemo, useState } from "react";
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

