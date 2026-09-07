import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { AnalysisSnapshotCard } from "../components/debate/AnalysisSnapshotCard";
import { JudgeSummaryCard } from "../components/debate/JudgeSummaryCard";
import { LegacyClaimCard } from "../components/debate/LegacyClaimCard";
import { BackButton, LoadingView } from "../components/common";
import { appStyles as styles, colors, spacing } from "../theme";
import type { AnalysisResponse, Claim } from "../types";

type LegacyDebateScreenProps = {
  analysis: AnalysisResponse | null;
  loading: boolean;
  onBack: () => void;
  onExamine: (claim: Claim) => void;
  onRun: () => void;
  ticker: string;
};

const fallbackStyles = StyleSheet.create({
  notice: {
    backgroundColor: colors.surface.information,
    borderColor: colors.border.information,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: spacing.lg,
    padding: spacing.md,
  },
  noticeTitle: {
    color: colors.content.primary,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.7,
    marginBottom: 4,
  },
  noticeBody: {
    color: colors.content.secondary,
    fontSize: 12,
    lineHeight: 18,
  },
});

export function LegacyDebateScreen({
  ticker,
  analysis,
  loading,
  onBack,
  onExamine,
  onRun,
}: LegacyDebateScreenProps) {
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  if (loading && !analysis) return <LoadingView label="Running the legacy fallback evidence workflow..." onBack={onBack} />;
  return (
    <ScrollView contentContainerStyle={[styles.page, styles.readingPage]}>
      <BackButton onPress={onBack} />
      <View accessibilityLiveRegion="polite" style={fallbackStyles.notice}>
        <Text style={fallbackStyles.noticeTitle}>LEGACY FALLBACK · NOT V2 CANONICAL DEBATE</Text>
        <Text style={fallbackStyles.noticeBody}>This saved-analysis view is retained for compatibility. New sessions use V2 only when that experience is explicitly enabled.</Text>
      </View>
      <View style={styles.detailHeader}>
        <View><Text style={styles.eyebrow}>LEGACY TRACE · {ticker}</Text><Text accessibilityRole="header" style={styles.detailTitle}>Classic Debate</Text></View>
        <Text accessibilityLabel="Legacy fallback status" style={styles.liveDot}>●</Text>
      </View>
      {!analysis ? (
        <View style={styles.emptyCard}>
          <Text accessibilityRole="header" style={styles.cardTitle}>No legacy analysis run yet</Text>
          <Text style={styles.mutedText}>Run the deterministic fallback workflow to see the Bull, Bear, Judge, and Guardrail agents.</Text>
          <Pressable accessibilityHint="Runs the deterministic analysis workflow for this security." accessibilityRole="button" style={styles.primaryButton} onPress={onRun}><Text style={styles.primaryButtonText}>Run analysis</Text></Pressable>
        </View>
      ) : (
        <>
          <AnalysisSnapshotCard snapshot={analysis.snapshot} />
          <JudgeSummaryCard judge={analysis.judge} />
          <LegacyClaimCard claim={analysis.bull} closeDate={analysis.snapshot.price.as_of} evidence={analysis.evidence} onExamine={onExamine} />
          <LegacyClaimCard claim={analysis.bear} closeDate={analysis.snapshot.price.as_of} evidence={analysis.evidence} onExamine={onExamine} />
          <View style={styles.diagnosticDisclosure}>
            <Pressable
              accessibilityLabel={`${showDiagnostics ? "Hide" : "Show"} analysis technical details`}
              accessibilityRole="button"
              accessibilityState={{ expanded: showDiagnostics }}
              onPress={() => setShowDiagnostics((current) => !current)}
              style={styles.diagnosticDisclosureButton}
            >
              <Text style={styles.diagnosticDisclosureTitle}>Analysis technical details</Text>
              <Text style={styles.diagnosticDisclosureAction}>{showDiagnostics ? "Hide" : "Show"}</Text>
            </Pressable>
            {showDiagnostics ? (
              <View style={styles.diagnosticPanel}>
                <View style={styles.rowBetween}><Text style={styles.cardLabel}>AGENT TRACE</Text><Text style={styles.mutedText}>{analysis.token_usage.model_name}</Text></View>
                {analysis.trace.map((step) => <Text key={step.step} style={styles.traceLine}>✓ {step.step.replace(/_/g, " ")} — {step.detail}</Text>)}
                <Text style={styles.traceLine}>Token ledger: {analysis.token_usage.total_tokens} demo tokens</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.safeNote}>{analysis.disclaimer}</Text>
        </>
      )}
    </ScrollView>
  );
}
