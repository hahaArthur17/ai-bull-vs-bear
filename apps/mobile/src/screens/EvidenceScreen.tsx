import { ScrollView, Text, View } from "react-native";

import { BackButton } from "../components/common";
import { appStyles as styles } from "../theme";
import type { EvidenceItem } from "../types";

type EvidenceScreenProps = {
  ticker: string;
  evidence: EvidenceItem[];
  onBack: () => void;
};

export function EvidenceScreen({ ticker, evidence, onBack }: EvidenceScreenProps) {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <BackButton onPress={onBack} />
      <Text style={styles.eyebrow}>{ticker} · WHAT THE AGENTS USED</Text>
      <Text style={styles.detailTitle}>Evidence Board</Text>
      {evidence.length === 0 ? <Text style={styles.mutedText}>No evidence is available yet.</Text> : evidence.map((item) => (
        <View key={item.id} style={styles.evidenceCard}>
          <View style={styles.rowBetween}><Text style={styles.evidenceTag}>{item.id}</Text><Text style={styles.mutedText}>{item.source_type}</Text></View>
          <Text style={styles.cardTitle}>{item.title}</Text>
          <Text style={styles.mutedText}>{item.excerpt}</Text>
          <Text style={styles.sourceText}>
            {typeof item.metadata.source === "string" ? item.metadata.source : "cached source"} · {item.published_at || "undated"}
          </Text>
          <Text style={[
            styles.freshnessText,
            item.freshness.status === "current" && styles.freshnessCurrent,
            item.freshness.status === "stale" && styles.freshnessStale,
          ]}>
            {item.freshness.status === "current"
              ? `Current · ${item.freshness.age_days ?? 0}d old`
              : item.freshness.status === "stale"
                ? `Stale · ${item.freshness.age_days ?? "?"}d old`
                : "Freshness unavailable"}
          </Text>
        </View>
      ))}
      <Text style={styles.safeNote}>Evidence is shown for interpretation, not as a recommendation.</Text>
    </ScrollView>
  );
}
