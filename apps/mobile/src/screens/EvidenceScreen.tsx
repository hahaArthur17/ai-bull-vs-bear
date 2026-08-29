import { Linking, Pressable, ScrollView, Text, View } from "react-native";

import { BackButton, FailureView, LoadingView } from "../components/common";
import { presentEvidence } from "../evidencePresentation";
import { appStyles as styles } from "../theme";
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
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>{ticker} · WHAT THE AGENTS USED</Text>
      <Text style={styles.detailTitle}>Evidence Board</Text>
      <Text style={styles.evidenceIntro}>Each reference retains its identifier, source, publication date, and freshness assessment.</Text>
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
  return (
    <View style={styles.evidenceCard}>
      <View style={styles.rowBetween}><Text style={styles.evidenceTag}>{item.id}</Text><Text style={styles.mutedText}>{item.source_type}</Text></View>
      <Text style={styles.cardTitle}>{item.title}</Text>
      <Text style={styles.mutedText}>{item.excerpt}</Text>
      <View style={styles.evidenceMetadata}>
        <Text style={styles.sourceText}>Source · {detail.source}</Text>
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
          onPress={() => { void Linking.openURL(item.url!).catch(() => undefined); }}
          style={styles.evidenceLink}
        >
          <Text style={styles.evidenceLinkText}>Open cited source ↗</Text>
        </Pressable>
      ) : <Text style={styles.evidenceLinkUnavailable}>Source link unavailable</Text>}
    </View>
  );
}
