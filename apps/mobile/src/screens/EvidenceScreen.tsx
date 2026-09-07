import { useState } from "react";
import { Linking, Pressable, ScrollView, Text, View } from "react-native";

import { BackButton, FailureView, LoadingView } from "../components/common";
import { isSafeEvidenceDestination, presentEvidence } from "../evidencePresentation";
import { appStyles as styles, colors, interaction, radii, spacing } from "../theme";
import type { EvidenceItem } from "../types";

type EvidenceScreenProps = {
  ticker: string;
  evidence: EvidenceItem[];
  error: string;
  loading: boolean;
  onBack: () => void;
  onRetry: () => void;
};

export function EvidenceScreen({ ticker, evidence, error, loading, onBack, onRetry }: EvidenceScreenProps) {
  if (loading) return <LoadingView label="Loading dated evidence..." onBack={onBack} />;
  if (error) return <FailureView message={error} onBack={onBack} onRetry={onRetry} />;
  return (
    <ScrollView contentContainerStyle={[styles.page, styles.readingPage]}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>{ticker} · WHAT THE AGENTS USED</Text>
      <View style={styles.rowBetween}>
        <Text style={styles.detailTitle}>Evidence Board</Text>
        <View accessibilityLabel={`${evidence.length} evidence items`} style={{ backgroundColor: colors.surface.information, borderColor: colors.border.information, borderRadius: radii.pill, borderWidth: 1, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs }}>
          <Text style={styles.evidenceTag}>{evidence.length} ITEM{evidence.length === 1 ? "" : "S"}</Text>
        </View>
      </View>
      <Text style={styles.evidenceIntro}>References used by the agents. Every item keeps its identifier, source, publication date, and freshness assessment.</Text>
      {evidence.length === 0 ? (
        <View accessibilityLiveRegion="polite" style={styles.evidenceStateCard}>
          <Text style={styles.cardTitle}>No evidence is available yet</Text>
          <Text style={styles.mutedText}>This research snapshot has no dated evidence to display. Return to the workspace and try loading the research bundle again.</Text>
        </View>
      ) : evidence.map((item) => <EvidenceCard key={item.id} item={item} />)}
      <Text style={styles.safeNote}>Evidence is shown for interpretation, not as a recommendation.</Text>
    </ScrollView>
  );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
  const detail = presentEvidence(item);
  const [linkFeedback, setLinkFeedback] = useState("");

  const openSource = async () => {
    if (!isSafeEvidenceDestination(item.url)) {
      setLinkFeedback("This source link cannot be opened safely. The cited URL is unavailable or uses an unsupported address.");
      return;
    }
    try {
      const canOpen = await Linking.canOpenURL(item.url);
      if (!canOpen) throw new Error("Unsupported source URL");
      await Linking.openURL(item.url);
      setLinkFeedback("");
    } catch {
      setLinkFeedback("Unable to open this cited source. Your research remains unchanged; try the source again later.");
    }
  };

  return (
    <View accessibilityLabel={`Evidence ${item.id}: ${item.title}`} style={styles.evidenceCard}>
      <View style={styles.rowBetween}>
        <Text style={styles.evidenceTag}>{item.id}</Text>
        <View style={{ backgroundColor: colors.surface.subtle, borderColor: colors.border.subtle, borderRadius: radii.sm, borderWidth: 1, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs }}>
          <Text style={styles.evidenceTag}>{item.source_type}</Text>
        </View>
      </View>
      <Text style={styles.cardTitle}>{item.title}</Text>
      <Text style={styles.mutedText}>{item.excerpt}</Text>
      <View style={styles.evidenceMetadata}>
        <Text style={[styles.sourceText, { marginTop: 0 }]}>Source · {detail.source}</Text>
        <Text style={styles.sourceText}>Published · {detail.date}</Text>
        <Text style={[
          styles.freshnessText,
          detail.tone === "current" && styles.freshnessCurrent,
          detail.tone === "stale" && styles.freshnessStale,
        ]}>Freshness · {detail.freshness}</Text>
      </View>
      {item.url ? (
        <Pressable
          accessibilityHint="Opens the cited source in the browser."
          accessibilityLabel={`Open source for evidence ${item.id}`}
          accessibilityRole="link"
          onPress={() => { void openSource(); }}
          style={[styles.evidenceLink, { borderColor: colors.border.subtle, borderRadius: radii.md, borderWidth: 1, minWidth: interaction.minTargetSize, paddingHorizontal: spacing.md }]}
        >
          <Text style={styles.evidenceLinkText}>Open cited source ↗</Text>
        </Pressable>
      ) : <Text style={styles.evidenceLinkUnavailable}>Source link unavailable</Text>}
      {linkFeedback ? <Text accessibilityLiveRegion="polite" style={[styles.mutedText, { backgroundColor: colors.surface.subtle, borderColor: colors.border.subtle, borderRadius: radii.sm, borderWidth: 1, marginTop: spacing.sm, padding: spacing.sm }]}>{linkFeedback}</Text> : null}
    </View>
  );
}
