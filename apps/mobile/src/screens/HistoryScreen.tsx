import React from "react";
import { ScrollView, Text, useWindowDimensions, View } from "react-native";

import { FocusablePressable } from "../components/common";
import { debateHistoryCopy } from "../debateHistoryView";
import { isWideHistoryLayout } from "../historyLayout";
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
  const { width: viewportWidth } = useWindowDimensions();
  const isWideLayout = isWideHistoryLayout(viewportWidth);
  return (
    <ScrollView contentContainerStyle={[styles.page, styles.readingPage]}>
      <Text style={styles.eyebrow}>SAVED RESEARCH · REOPENABLE</Text>
      <Text accessibilityRole="header" style={styles.detailTitle}>History</Text>
      <Text style={styles.historyIntro}>
        Reopen a canonical V2 Debate, its interim or final Judge, or a classic analysis fallback.
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
          <Text accessibilityRole="header" style={styles.historySectionTitle}>V2 CANONICAL DEBATES</Text>
          {debates.map((session) => {
            const copy = debateHistoryCopy(session);
            return (
              <FocusablePressable
                key={session.id}
                style={[styles.historyRow, !isWideLayout && styles.historyRowStacked]}
                onPress={() => onOpenDebate(session)}
                accessibilityRole="button"
                accessibilityLabel={`Open ${session.ticker} Debate: ${copy.label}`}
              >
                <View style={[styles.historyCopy, isWideLayout && styles.historyCopyWide]}>
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
                <View style={[styles.historyAction, isWideLayout && styles.historyActionWide]}>
                  <Text style={styles.examineLink}>{copy.action} →</Text>
                </View>
              </FocusablePressable>
            );
          })}
        </>
      ) : null}
      {history.length > 0 ? <Text accessibilityRole="header" style={styles.historySectionTitle}>LEGACY CLASSIC ANALYSES · FALLBACK</Text> : null}
      {history.map((item) => (
        <FocusablePressable
          accessibilityLabel={`Open classic ${item.ticker} analysis`}
          accessibilityRole="button"
          key={item.analysis_id}
          style={[styles.historyRow, !isWideLayout && styles.historyRowStacked]}
          onPress={() => onOpen(item)}
        >
          <View style={[styles.historyCopy, isWideLayout && styles.historyCopyWide]}>
            <Text style={styles.stockTicker}>{item.ticker}</Text>
            <Text style={styles.historyTitle}>Legacy Bull, Bear, and Judge synthesis</Text>
            <Text style={styles.historyTimestamp}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
          <View style={[styles.historyAction, isWideLayout && styles.historyActionWide]}>
            <Text style={styles.examineLink}>Review →</Text>
          </View>
        </FocusablePressable>
      ))}
    </ScrollView>
  );
}
