import { ActivityIndicator, Text, View } from "react-native";
import type { DebateStreamSnapshot } from "../../debateStream";
import { debateStatusCopy } from "../../liveDebateView";
import { FocusablePressable } from "../common";
import { colors, screenStyles } from "./debateStyles";

const interruptionsEnabled = process.env.EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED === "true";

export function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "pending";
}

function statusColor(tone: ReturnType<typeof debateStatusCopy>["tone"]): string {
  if (tone === "active") return colors.cyan;
  if (tone === "success") return colors.bull;
  if (tone === "warning") return colors.warning;
  if (tone === "danger") return colors.danger;
  return colors.muted;
}

export function DebateStatusPanel({ snapshot }: { snapshot: DebateStreamSnapshot }) {
  const status = debateStatusCopy(snapshot);
  return (
    <View style={[screenStyles.statusCard, { borderLeftColor: statusColor(status.tone) }]}>
      <View style={screenStyles.rowBetween}>
        <Text style={[screenStyles.statusLabel, { color: statusColor(status.tone) }]}>
          {status.label}
        </Text>
        {snapshot.status === "connecting" || snapshot.status === "reconnecting" ? (
          <ActivityIndicator color={colors.cyan} size="small" />
        ) : null}
      </View>
      <Text style={screenStyles.statusDetail}>{status.detail}</Text>
      <View style={screenStyles.telemetryRow}>
        <Text style={screenStyles.telemetry}>
          {snapshot.jobId
            ? `JOB ${shortId(snapshot.jobId)}`
            : snapshot.jobStatus === "stage_completed"
              ? "JOB SETTLED"
              : "JOB NOT ACTIVE"}
        </Text>
        {snapshot.jobId ? (
          <Text style={screenStyles.telemetry}>ATTEMPT {snapshot.jobAttemptCount}</Text>
        ) : null}
        <Text style={screenStyles.telemetry}>EVENT {snapshot.lastSequence}</Text>
      </View>
    </View>
  );
}

export function DebateStopControl({
  canCancel,
  cancelling,
  onStop,
}: {
  canCancel: boolean;
  cancelling: boolean;
  onStop: () => void | Promise<void>;
}) {
  return canCancel || cancelling ? (
    <FocusablePressable
      disabled={!canCancel}
      style={[screenStyles.cancelButton, !canCancel && screenStyles.disabledButton]}
      onPress={() => void onStop()}
      accessibilityLabel="Stop the current Debate generation"
      accessibilityRole="button"
      accessibilityState={{ busy: cancelling, disabled: !canCancel }}
    >
      {cancelling ? <ActivityIndicator color={colors.bear} size="small" /> : null}
      <Text style={screenStyles.cancelText}>
        {cancelling
          ? "Confirming stop…"
          : interruptionsEnabled
            ? "Stop here"
            : "Stop this generation"}
      </Text>
    </FocusablePressable>
  ) : null;
}
