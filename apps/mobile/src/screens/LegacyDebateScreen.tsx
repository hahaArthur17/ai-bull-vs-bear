import { Pressable, ScrollView, Text, View } from "react-native";

import { AnalysisSnapshotCard } from "../components/debate/AnalysisSnapshotCard";
import { JudgeSummaryCard } from "../components/debate/JudgeSummaryCard";
import { LegacyClaimCard } from "../components/debate/LegacyClaimCard";
import { BackButton, LoadingView } from "../components/common";
import { appStyles as styles } from "../theme";
import type { AnalysisResponse, Claim } from "../types";

type LegacyDebateScreenProps = {
  analysis: AnalysisResponse | null;
  loading: boolean;
  onBack: () => void;
  onExamine: (claim: Claim) => void;
  onRun: () => void;
  ticker: string;
};

export function LegacyDebateScreen({
  ticker,
  analysis,
  loading,
  onBack,
  onExamine,
  onRun,
}: LegacyDebateScreenProps) {
  if (loading && !analysis) return <LoadingView label="Running the evidence workflow..." onBack={onBack} />;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <View style={styles.detailHeader}>
        <View><Text style={styles.eyebrow}>LIVE TRACE · {ticker}</Text><Text style={styles.detailTitle}>Debate Arena</Text></View>
        <Text style={styles.liveDot}>●</Text>
      </View>
      {!analysis ? (
        <View style={styles.emptyCard}>
          <Text style={styles.cardTitle}>No analysis run yet</Text>
          <Text style={styles.mutedText}>Run the deterministic demo workflow to see the Bull, Bear, Judge, and Guardrail agents.</Text>
          <Pressable accessibilityHint="Runs the deterministic analysis workflow for this security." accessibilityRole="button" style={styles.primaryButton} onPress={onRun}><Text style={styles.primaryButtonText}>Run analysis</Text></Pressable>
        </View>
      ) : (
        <>
          <AnalysisSnapshotCard snapshot={analysis.snapshot} />
          <JudgeSummaryCard judge={analysis.judge} />
          <LegacyClaimCard claim={analysis.bull} closeDate={analysis.snapshot.price.as_of} evidence={analysis.evidence} onExamine={onExamine} />
          <LegacyClaimCard claim={analysis.bear} closeDate={analysis.snapshot.price.as_of} evidence={analysis.evidence} onExamine={onExamine} />
          <View style={styles.traceCard}>
            <View style={styles.rowBetween}><Text style={styles.cardLabel}>AGENT TRACE</Text><Text style={styles.mutedText}>{analysis.token_usage.model_name}</Text></View>
            {analysis.trace.map((step) => <Text key={step.step} style={styles.traceLine}>✓ {step.step.replace(/_/g, " ")} — {step.detail}</Text>)}
            <Text style={styles.traceLine}>Token ledger: {analysis.token_usage.total_tokens} demo tokens</Text>
          </View>
          <Text style={styles.safeNote}>{analysis.disclaimer}</Text>
        </>
      )}
    </ScrollView>
  );
}
