import { Text } from "react-native";

import { presentEvidence } from "../../evidencePresentation";
import { appStyles as styles } from "../../theme";
import type { EvidenceItem } from "../../types";

export function EvidenceCitation({
  evidenceId,
  item,
  closeDate,
}: {
  evidenceId: string;
  item: EvidenceItem | undefined;
  closeDate: string;
}) {
  const detail = item ? presentEvidence(item) : null;
  const date = detail?.date ?? (item?.source_type === "technical" ? closeDate : "Date unavailable");
  return (
    <Text style={styles.evidenceIds}>
      Evidence · {evidenceId} · {item?.source_type ?? "unavailable"} · Source {detail?.source ?? "unavailable"} · {date} · {detail?.freshness ?? "Freshness unavailable"}
    </Text>
  );
}
