import { Text, View } from "react-native";

import { appStyles as styles } from "../../theme";
import type { AnalysisResponse } from "../../types";

export function JudgeSummaryCard({ judge }: { judge: AnalysisResponse["judge"] }) {
  return (
    <View style={styles.judgeCard}>
      <View style={styles.rowBetween}><Text style={styles.cardLabel}>JUDGE SYNTHESIS</Text><Text style={styles.confidence}>{judge.evidence_strength} evidence</Text></View>
      <Text style={styles.judgeTitle}>{judge.summary}</Text>
      <Text style={styles.mutedText}>{judge.uncertainty}</Text>
      <Text style={styles.riskPill}>Risk level · {judge.risk_level}</Text>
    </View>
  );
}
