import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { debateHistoryCopy } from "../debateHistoryView";
import { appStyles as styles } from "../theme";
import type { AnalysisResponse, DebateSessionSummary } from "../types";


type HistoryScreenProps = {
  history: AnalysisResponse[];
  debates: DebateSessionSummary[];
  onOpen: (item: AnalysisResponse) => void;
  onOpenDebate: (session: DebateSessionSummary) => void;
};


export function HistoryScreen({
  history,
  debates,
  onOpen,
  onOpenDebate,
}: HistoryScreenProps) {
  const hasHistory = history.length > 0 || debates.length > 0;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>ANALYSIS RUNS</Text>
      <Text style={styles.detailTitle}>History</Text>
      {!hasHistory ? (
        <View style={styles.emptyCard}>
          <Text style={styles.cardTitle}>No runs yet</Text>
          <Text style={styles.mutedText}>
            Start a Bull vs Bear debate from a stock detail page.
          </Text>
        </View>
      ) : null}
      {debates.length > 0 ? (
        <>
          <Text style={styles.historySectionTitle}>V2 DEBATES</Text>
          {debates.map((session) => {
            const copy = debateHistoryCopy(session);
            return (
              <Pressable
                key={session.id}
                style={styles.historyRow}
                onPress={() => onOpenDebate(session)}
                accessibilityRole="button"
                accessibilityLabel={`Open ${session.ticker} Debate: ${copy.label}`}
              >
                <View style={styles.historyCopy}>
                  <Text style={styles.stockTicker}>{session.ticker}</Text>
                  <Text style={styles.historyStatus}>{copy.label}</Text>
                  <Text style={styles.mutedText}>{copy.detail}</Text>
                  <Text style={styles.mutedText}>
                    {new Date(session.updated_at).toLocaleString()}
                  </Text>
                </View>
                <Text style={styles.examineLink}>Open →</Text>
              </Pressable>
            );
          })}
        </>
      ) : null}
      {history.length > 0 ? <Text style={styles.historySectionTitle}>LEGACY ANALYSES</Text> : null}
      {history.map((item) => (
        <Pressable key={item.analysis_id} style={styles.historyRow} onPress={() => onOpen(item)}>
          <View><Text style={styles.stockTicker}>{item.ticker}</Text><Text style={styles.mutedText}>{new Date(item.created_at).toLocaleString()}</Text></View>
          <Text style={styles.examineLink}>Open →</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
