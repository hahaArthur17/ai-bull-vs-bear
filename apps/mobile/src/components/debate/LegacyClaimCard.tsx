import { Pressable, Text, View } from "react-native";

import { AgentStatusBadge } from "./AgentStatusBadge";
import { EvidenceCitation } from "./EvidenceCitation";
import { formatMarketDate } from "../../dateFormat";
import { appStyles as styles, palette } from "../../theme";
import type { Claim, EvidenceItem } from "../../types";

export function LegacyClaimCard({
  claim,
  closeDate,
  evidence,
  onExamine,
}: {
  claim: Claim;
  closeDate: string;
  evidence: EvidenceItem[];
  onExamine: (claim: Claim) => void;
}) {
  const evidenceById = new Map(evidence.map((item) => [item.id, item]));
  const isBull = claim.agent === "bull";
  return (
    <View style={[styles.claimCard, { borderLeftColor: isBull ? palette.bull : palette.bear }]}>
      <View style={styles.rowBetween}><AgentStatusBadge agent={claim.agent} /><Text style={styles.mutedText}>{claim.confidence} confidence</Text></View>
      <Text style={styles.claimText}>{claim.text}</Text>
      <Text style={styles.claimCloseDate}>Market close · {formatMarketDate(closeDate)}</Text>
      <View style={styles.claimCitations}>
        {claim.evidence_ids.map((id) => <EvidenceCitation key={id} evidenceId={id} item={evidenceById.get(id)} closeDate={closeDate} />)}
      </View>
      <Pressable accessibilityHint="Opens focused questions about this claim." accessibilityRole="button" onPress={() => onExamine(claim)}><Text style={styles.examineLink}>Tap to cross-examine →</Text></Pressable>
    </View>
  );
}
