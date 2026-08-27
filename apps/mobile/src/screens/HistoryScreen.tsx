import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { appStyles as styles } from "../theme";
import type { AnalysisResponse } from "../types";


export function HistoryScreen({ history, onOpen }: { history: AnalysisResponse[]; onOpen: (item: AnalysisResponse) => void }) {
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

