import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { debateHistoryCopy } from "../debateHistoryView";
import { appStyles as styles } from "../theme";
import type { AnalysisResponse, DebateSessionSummary } from "../types";

const historyStatusStyle = {
  final: styles.historyStatusFinal,
  interim: styles.historyStatusInterim,
  active: styles.historyStatusActive,
  cancelled: styles.historyStatusCancelled,
  failed: styles.historyStatusFailed,
};

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
      <Text style={styles.eyebrow}>SAVED RESEARCH</Text>
      <Text style={styles.detailTitle}>History</Text>
      <Text style={styles.historyIntro}>
        Reopen a canonical Debate, its interim or final Judge, or a classic analysis run.
      </Text>
      {!hasHistory ? (
        <View style={styles.emptyCard}>
          <Text accessibilityRole="header" style={styles.cardTitle}>Your research history is empty</Text>
          <Text style={styles.mutedText}>
            Choose a Debate-ready stock from Signals, review its evidence, then start Bull vs Bear. Completed runs stay here for review.
          </Text>
        </View>
      ) : null}
      {debates.length > 0 ? (
        <>
          <Text accessibilityRole="header" style={styles.historySectionTitle}>CANONICAL DEBATES</Text>
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
                  <View style={styles.historyRowHeader}>
                    <Text style={styles.stockTicker}>{session.ticker}</Text>
                    <Text style={[styles.historyStatus, historyStatusStyle[copy.kind]]}>{copy.label}</Text>
                  </View>
                  <Text style={styles.historyTitle}>{copy.title}</Text>
                  <Text style={styles.mutedText}>{copy.detail}</Text>
                  <Text style={styles.historyTimestamp}>
                    {new Date(session.updated_at).toLocaleString()}
                  </Text>
                </View>
                <Text style={styles.examineLink}>{copy.action} →</Text>
              </Pressable>
            );
          })}
        </>
      ) : null}
      {history.length > 0 ? <Text accessibilityRole="header" style={styles.historySectionTitle}>CLASSIC ANALYSES</Text> : null}
      {history.map((item) => (
        <Pressable
          accessibilityLabel={`Open classic ${item.ticker} analysis`}
          accessibilityRole="button"
          key={item.analysis_id}
          style={styles.historyRow}
          onPress={() => onOpen(item)}
        >
          <View style={styles.historyCopy}>
            <Text style={styles.stockTicker}>{item.ticker}</Text>
            <Text style={styles.historyTitle}>Bull, Bear, and Judge synthesis</Text>
            <Text style={styles.historyTimestamp}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
          <Text style={styles.examineLink}>Review →</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
