import { Text, View } from "react-native";

import { formatMarketDate } from "../../dateFormat";
import { formatMacroValue } from "../../research/chartMath";
import { appStyles as styles } from "../../theme";
import type { AnalysisResponse } from "../../types";

export function AnalysisSnapshotCard({ snapshot }: { snapshot: AnalysisResponse["snapshot"] }) {
  return (
    <View style={styles.snapshotCard}>
      <Text style={styles.cardLabel}>ANALYSIS SNAPSHOT</Text>
      <Text style={styles.snapshotTitle}>{formatMarketDate(snapshot.price.as_of)} close · ${snapshot.price.close.toFixed(2)}</Text>
      <Text style={styles.mutedText}>
        {snapshot.price.source === "daily_market_cache" && !snapshot.price.is_stale
          ? "Verified daily market cache"
          : "Price cache is unavailable or stale; interpret this run cautiously."}
      </Text>
      <Text style={styles.snapshotDetail}>
        {snapshot.included_evidence_ids.length} cited item(s)
        {snapshot.excluded_external_evidence_count > 0
          ? ` · ${snapshot.excluded_external_evidence_count} stale or undated item(s) excluded`
          : " · all retrieved external context passed its freshness check"}
      </Text>
      {snapshot.missing_current_evidence.length > 0 ? (
        <Text style={styles.snapshotWarning}>Missing current {snapshot.missing_current_evidence.join(" and ")} evidence.</Text>
      ) : null}
      {snapshot.macro_context.length > 0 ? (
        <View style={styles.debateMacroSnapshot}>
          <Text style={styles.debateMacroLabel}>MARKET BACKGROUND AT THIS CLOSE · NOT CAUSAL</Text>
          {snapshot.macro_context.map((item) => (
            <Text key={item.code} style={styles.debateMacroItem}>
              {item.name} · {formatMacroValue(item.value, item.unit)} · {formatMarketDate(item.observation_date)} · {item.source.toUpperCase()}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}
