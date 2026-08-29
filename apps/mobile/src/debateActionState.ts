export type DebateActionStatus = {
  detail: string;
  label: "Cancelling" | "Explaining" | "Queueing challenge";
} | null;

export function debateActionStatus({
  cancelling,
  challenging,
  explaining,
}: {
  cancelling: boolean;
  challenging: boolean;
  explaining: boolean;
}): DebateActionStatus {
  if (cancelling) return { label: "Cancelling", detail: "Late generation output will be discarded when the active generation is invalidated." };
  if (challenging) return { label: "Queueing challenge", detail: "The exact passage and your question are being committed before Round 2 can start." };
  if (explaining) return { label: "Explaining", detail: "Explanation reads the selected complete message and does not change the Debate." };
  return null;
}
