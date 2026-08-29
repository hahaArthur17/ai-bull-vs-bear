import { Text } from "react-native";

import { appStyles as styles, palette } from "../../theme";
import type { Claim } from "../../types";

export function AgentStatusBadge({ agent }: { agent: Claim["agent"] }) {
  const isBull = agent === "bull";
  return (
    <Text style={[styles.cardLabel, { color: isBull ? palette.bull : palette.bear }]}>
      {isBull ? "BULL AGENT" : "BEAR AGENT"}
    </Text>
  );
}
