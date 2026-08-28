import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api, createDebateStreamClient } from "../api";
import {
  createCanonicalDebateSnapshot,
} from "../debateStream";
import type {
  DebateDraft,
  DebateStreamClient,
  DebateStreamSnapshot,
} from "../debateStream";
import {
  canCancelDebate,
  canChallengeDebate,
  debateStatusCopy,
} from "../liveDebateView";
import type {
  DebateMessageRecord,
  DebateMutationResponse,
} from "../types";

type LiveDebateScreenProps = {
  ticker: string;
  initialDetail: DebateMutationResponse;
  onBack: () => void;
};

const colors = {
  background: "#07111f",
  surface: "#0d1b2d",
  elevated: "#12243a",
  line: "#263c55",
  text: "#edf7ff",
  muted: "#91a6ba",
  cyan: "#36d4e8",
  bull: "#4bd49b",
  bear: "#ff7185",
  judge: "#c8a8ff",
  warning: "#f5bd5c",
  danger: "#ff7185",
} as const;

function newIdempotencyKey(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "pending";
}

function rolePresentation(role: DebateMessageRecord["message"]["role"] | DebateDraft["role"]) {
  if (role === "bull") return { label: "BULL", color: colors.bull };
  if (role === "bear") return { label: "BEAR", color: colors.bear };
  if (role === "judge") return { label: "NEUTRAL JUDGE", color: colors.judge };
  if (role === "user") return { label: "YOUR QUESTION", color: colors.cyan };
  if (role === "explainer") return { label: "EXPLAINER", color: colors.warning };
  return { label: "SYSTEM", color: colors.muted };
}

function statusColor(tone: ReturnType<typeof debateStatusCopy>["tone"]): string {
  if (tone === "active") return colors.cyan;
  if (tone === "success") return colors.bull;
  if (tone === "warning") return colors.warning;
  if (tone === "danger") return colors.danger;
  return colors.muted;
}

export function LiveDebateScreen({
  ticker,
  initialDetail,
  onBack,
}: LiveDebateScreenProps) {
  const [snapshot, setSnapshot] = useState<DebateStreamSnapshot>(() =>
    createCanonicalDebateSnapshot(initialDetail),
  );
  const [streamEpoch, setStreamEpoch] = useState(0);
  const [connectionError, setConnectionError] = useState("");
  const [actionError, setActionError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [challenging, setChallenging] = useState(false);
  const [challengeTarget, setChallengeTarget] = useState<DebateMessageRecord | null>(null);
  const [selectedText, setSelectedText] = useState("");
  const [question, setQuestion] = useState("");
  const challengeKey = useRef<string | null>(null);
  const streamClient = useRef<DebateStreamClient | null>(null);
  const sessionId = initialDetail.session.id;

  useEffect(() => {
    setSnapshot(createCanonicalDebateSnapshot(initialDetail));
    setConnectionError("");
    setActionError("");
    setChallengeTarget(null);
    setSelectedText("");
    setQuestion("");
    challengeKey.current = null;
  }, [sessionId]);

  useEffect(() => {
    let mounted = true;
    const client = createDebateStreamClient(sessionId, (next) => {
      if (mounted) setSnapshot(next);
    });
    streamClient.current = client;
    setConnectionError("");
    void client.start().catch(() => {
      if (mounted) {
        setConnectionError(
          "Live updates could not start. Canonical completed messages remain safe.",
        );
      }
    });
    return () => {
      mounted = false;
      client.stop();
      if (streamClient.current === client) streamClient.current = null;
    };
  }, [sessionId, streamEpoch]);

  const status = debateStatusCopy(snapshot);
  const drafts = Object.values(snapshot.drafts);
  const canCancel = canCancelDebate(snapshot) && !cancelling;
  const canChallenge = canChallengeDebate(snapshot);
  const selectedTextIsValid = challengeTarget !== null
    && selectedText.trim().length > 0
    && challengeTarget.message.content.includes(selectedText.trim());
  const canSubmitChallenge = canChallenge
    && selectedTextIsValid
    && question.trim().length > 0
    && !challenging;

  const selectChallengeTarget = (record: DebateMessageRecord) => {
    setChallengeTarget(record);
    setSelectedText(record.message.content.slice(0, 500));
    setActionError("");
    challengeKey.current = null;
  };

  const cancelDebate = async () => {
    if (!snapshot.activeGenerationId || !canCancel) return;
    setCancelling(true);
    setActionError("");
    try {
      const detail = await api.cancelDebate(sessionId, snapshot.activeGenerationId);
      setSnapshot((current) => createCanonicalDebateSnapshot(
        detail,
        current.lastSequence,
        current.status,
      ));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not cancel this Debate.");
    } finally {
      setCancelling(false);
    }
  };

  const submitChallenge = async () => {
    if (!challengeTarget || !canSubmitChallenge) return;
    setChallenging(true);
    setActionError("");
    challengeKey.current ||= newIdempotencyKey("round2");
    try {
      const detail = await api.challengeDebate(sessionId, {
        selectedMessageId: challengeTarget.message.id,
        selectedText: selectedText.trim(),
        question: question.trim(),
        idempotencyKey: challengeKey.current,
      });
      setSnapshot(createCanonicalDebateSnapshot(detail));
      setChallengeTarget(null);
      setSelectedText("");
      setQuestion("");
      challengeKey.current = null;
      setStreamEpoch((current) => current + 1);
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Could not start the second Debate round.",
      );
    } finally {
      setChallenging(false);
    }
  };

  return (
    <ScrollView
      style={screenStyles.scroll}
      contentContainerStyle={screenStyles.page}
      accessibilityLabel={`${ticker} live Bull versus Bear Debate`}
    >
      <Pressable onPress={onBack} style={screenStyles.backButton} accessibilityRole="button">
        <Text style={screenStyles.backText}>← Market snapshot</Text>
      </Pressable>

      <View style={screenStyles.headerRow}>
        <View style={screenStyles.headerCopy}>
          <Text style={screenStyles.eyebrow}>LIVE DEBATE V2 · {ticker}</Text>
          <Text style={screenStyles.title}>Bull / Bear Arena</Text>
          <Text style={screenStyles.sessionMeta}>
            Session {shortId(sessionId)} · {initialDetail.execution_mode === "queued" ? "DURABLE QUEUE" : "SYNC PREVIEW"}
          </Text>
        </View>
        <View style={screenStyles.liveBadge}>
          <View style={screenStyles.liveDot} />
          <Text style={screenStyles.liveText}>{snapshot.status.toUpperCase()}</Text>
        </View>
      </View>

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

      {connectionError ? (
        <View style={screenStyles.warningCard}>
          <Text style={screenStyles.warningText}>{connectionError}</Text>
          <Pressable
            style={screenStyles.inlineButton}
            onPress={() => setStreamEpoch((current) => current + 1)}
          >
            <Text style={screenStyles.inlineButtonText}>Reconnect</Text>
          </Pressable>
        </View>
      ) : null}

      {actionError ? (
        <View style={screenStyles.errorCard}>
          <Text style={screenStyles.errorText}>{actionError}</Text>
        </View>
      ) : null}

      <View style={screenStyles.sectionHeader}>
        <Text style={screenStyles.sectionTitle}>Debate transcript</Text>
        <Text style={screenStyles.sectionMeta}>
          {snapshot.canonicalMessages.length} durable · {drafts.length} streaming
        </Text>
      </View>

      {snapshot.canonicalMessages.length === 0 && drafts.length === 0 ? (
        <View style={screenStyles.emptyCard}>
          <Text style={screenStyles.emptyTitle}>The transcript is intentionally empty</Text>
          <Text style={screenStyles.emptyText}>
            Queue admission returned before generation. Messages will appear here only after a
            Worker starts; partial output stays visually distinct from durable output.
          </Text>
        </View>
      ) : null}

      {snapshot.canonicalMessages.map((record) => (
        <MessageCard
          key={record.message.id}
          record={record}
          challengeEnabled={canChallenge}
          selected={challengeTarget?.message.id === record.message.id}
          onChallenge={() => selectChallengeTarget(record)}
        />
      ))}

      {drafts.map((draft) => <DraftCard key={draft.messageId} draft={draft} />)}

      {canChallenge ? (
        <View style={screenStyles.challengePanel}>
          <Text style={screenStyles.challengeEyebrow}>INTERIM JUDGE PAUSE</Text>
          <Text style={screenStyles.challengeTitle}>Direct the second round</Text>
          <Text style={screenStyles.challengeHelp}>
            Choose a completed Bull, Bear, or Judge message, keep an exact quoted passage, and ask
            a question. The question and Round 2 job are committed atomically.
          </Text>
          {challengeTarget ? (
            <>
              <Text style={screenStyles.inputLabel}>
                QUOTED PASSAGE · {rolePresentation(challengeTarget.message.role).label}
              </Text>
              <TextInput
                value={selectedText}
                onChangeText={setSelectedText}
                maxLength={500}
                multiline
                style={screenStyles.textArea}
                placeholder="Exact text from the selected message"
                placeholderTextColor={colors.muted}
              />
              {!selectedTextIsValid ? (
                <Text style={screenStyles.validationText}>
                  Keep an exact passage that occurs in the selected message.
                </Text>
              ) : null}
              <Text style={screenStyles.inputLabel}>YOUR QUESTION</Text>
              <TextInput
                value={question}
                onChangeText={setQuestion}
                maxLength={500}
                multiline
                style={screenStyles.textArea}
                placeholder="Which evidence should both sides reconsider?"
                placeholderTextColor={colors.muted}
              />
              <Pressable
                disabled={!canSubmitChallenge}
                style={[
                  screenStyles.challengeButton,
                  !canSubmitChallenge && screenStyles.disabledButton,
                ]}
                onPress={() => void submitChallenge()}
                accessibilityRole="button"
                accessibilityState={{ disabled: !canSubmitChallenge }}
              >
                {challenging ? <ActivityIndicator color={colors.background} size="small" /> : null}
                <Text style={screenStyles.challengeButtonText}>
                  {challenging ? "Queueing Round 2…" : "Queue Round 2 challenge"}
                </Text>
              </Pressable>
            </>
          ) : (
            <Text style={screenStyles.challengeEmpty}>
              Use the challenge action on a transcript card to select its argument.
            </Text>
          )}
        </View>
      ) : null}

      {canCancel || cancelling ? (
        <Pressable
          disabled={!canCancel}
          style={[screenStyles.cancelButton, !canCancel && screenStyles.disabledButton]}
          onPress={() => void cancelDebate()}
          accessibilityRole="button"
          accessibilityState={{ disabled: !canCancel }}
        >
          {cancelling ? <ActivityIndicator color={colors.bear} size="small" /> : null}
          <Text style={screenStyles.cancelText}>
            {cancelling ? "Requesting cancellation…" : "Stop this generation"}
          </Text>
        </Pressable>
      ) : null}

      <Text style={screenStyles.disclaimer}>
        Educational analysis only. Bull and Bear arguments are evidence-grounded scenarios, not
        trading instructions or predictions.
      </Text>
    </ScrollView>
  );
}

function MessageCard({
  record,
  challengeEnabled,
  selected,
  onChallenge,
}: {
  record: DebateMessageRecord;
  challengeEnabled: boolean;
  selected: boolean;
  onChallenge: () => void;
}) {
  const role = rolePresentation(record.message.role);
  const canTarget = challengeEnabled
    && record.message.role !== "user"
    && record.message.role !== "system"
    && record.message.role !== "explainer";
  return (
    <View style={[
      screenStyles.messageCard,
      { borderLeftColor: role.color },
      selected && screenStyles.selectedMessage,
    ]}>
      <View style={screenStyles.rowBetween}>
        <Text style={[screenStyles.roleLabel, { color: role.color }]}>{role.label}</Text>
        <Text style={screenStyles.messageMeta}>
          R{record.message.round_number} · E{record.message.exchange_number} · #{record.message.sequence_number}
        </Text>
      </View>
      <Text selectable style={screenStyles.messageText}>{record.message.content}</Text>
      {record.message.terms.length > 0 ? (
        <View style={screenStyles.termRow}>
          {record.message.terms.map((term) => (
            <View key={term} style={screenStyles.termChip}>
              <Text style={screenStyles.termText}>{term}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {record.citations.length > 0 ? (
        <Text style={screenStyles.citations}>
          EVIDENCE {record.citations.map((citation) => citation.evidence_id).join(" · ")}
        </Text>
      ) : null}
      {canTarget ? (
        <Pressable onPress={onChallenge} style={screenStyles.messageAction}>
          <Text style={screenStyles.messageActionText}>
            {selected ? "Selected for Round 2" : "Challenge this point →"}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function DraftCard({ draft }: { draft: DebateDraft }) {
  const role = rolePresentation(draft.role);
  return (
    <View style={[screenStyles.draftCard, { borderLeftColor: role.color }]}>
      <View style={screenStyles.rowBetween}>
        <Text style={[screenStyles.roleLabel, { color: role.color }]}>{role.label}</Text>
        <View style={screenStyles.streamingRow}>
          <ActivityIndicator color={colors.cyan} size="small" />
          <Text style={screenStyles.streamingText}>STREAMING</Text>
        </View>
      </View>
      <Text style={screenStyles.messageText}>
        {draft.content || "The agent has started this turn…"}
      </Text>
      <Text style={screenStyles.draftNote}>Temporary draft · not yet canonical</Text>
    </View>
  );
}

const screenStyles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.background },
  page: { backgroundColor: colors.background, padding: 20, paddingBottom: 130 },
  backButton: { alignSelf: "flex-start", paddingVertical: 8, marginBottom: 16 },
  backText: { color: colors.cyan, fontSize: 13, fontWeight: "800" },
  headerRow: { flexDirection: "row", justifyContent: "space-between", gap: 14, marginBottom: 18 },
  headerCopy: { flex: 1 },
  eyebrow: { color: colors.cyan, fontSize: 10, fontWeight: "900", letterSpacing: 1.6, marginBottom: 7 },
  title: { color: colors.text, fontSize: 30, lineHeight: 35, fontWeight: "900" },
  sessionMeta: { color: colors.muted, fontSize: 10, marginTop: 8, letterSpacing: 0.6 },
  liveBadge: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.elevated, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 7 },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.cyan },
  liveText: { color: colors.text, fontSize: 9, fontWeight: "900", letterSpacing: 0.8 },
  statusCard: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderLeftWidth: 4, borderRadius: 14, padding: 15, marginBottom: 14 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  statusLabel: { fontSize: 15, fontWeight: "900" },
  statusDetail: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 6 },
  telemetryRow: { flexDirection: "row", flexWrap: "wrap", gap: 12, borderTopColor: colors.line, borderTopWidth: 1, marginTop: 12, paddingTop: 10 },
  telemetry: { color: colors.muted, fontSize: 9, fontWeight: "800", letterSpacing: 0.8 },
  warningCard: { backgroundColor: "#332814", borderColor: "#6e5525", borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 12 },
  warningText: { color: colors.warning, fontSize: 12, lineHeight: 18 },
  inlineButton: { alignSelf: "flex-start", marginTop: 8, borderBottomColor: colors.warning, borderBottomWidth: 1 },
  inlineButtonText: { color: colors.warning, fontSize: 12, fontWeight: "800" },
  errorCard: { backgroundColor: "#351923", borderColor: "#6d2d3e", borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 12 },
  errorText: { color: colors.danger, fontSize: 12, lineHeight: 18 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 10, marginTop: 8, marginBottom: 12 },
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  sectionMeta: { color: colors.muted, fontSize: 10 },
  emptyCard: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderStyle: "dashed", borderRadius: 14, padding: 18, marginBottom: 12 },
  emptyTitle: { color: colors.text, fontSize: 14, fontWeight: "800", marginBottom: 7 },
  emptyText: { color: colors.muted, fontSize: 12, lineHeight: 19 },
  messageCard: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderLeftWidth: 4, borderRadius: 14, padding: 15, marginBottom: 11 },
  selectedMessage: { borderColor: colors.cyan, backgroundColor: "#102a3b" },
  draftCard: { backgroundColor: colors.elevated, borderColor: colors.cyan, borderWidth: 1, borderLeftWidth: 4, borderRadius: 14, padding: 15, marginBottom: 11 },
  roleLabel: { fontSize: 10, fontWeight: "900", letterSpacing: 1.1 },
  messageMeta: { color: colors.muted, fontSize: 9, fontWeight: "700" },
  messageText: { color: colors.text, fontSize: 14, lineHeight: 22, marginTop: 11 },
  termRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 12 },
  termChip: { borderColor: colors.line, borderWidth: 1, borderRadius: 12, paddingHorizontal: 8, paddingVertical: 4 },
  termText: { color: colors.muted, fontSize: 10 },
  citations: { color: colors.cyan, fontSize: 9, lineHeight: 15, fontWeight: "700", marginTop: 12 },
  messageAction: { alignSelf: "flex-start", marginTop: 13, paddingVertical: 5 },
  messageActionText: { color: colors.cyan, fontSize: 12, fontWeight: "800" },
  streamingRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  streamingText: { color: colors.cyan, fontSize: 9, fontWeight: "900", letterSpacing: 0.8 },
  draftNote: { color: colors.muted, fontSize: 10, fontStyle: "italic", marginTop: 9 },
  challengePanel: { backgroundColor: "#101d30", borderColor: colors.judge, borderWidth: 1, borderRadius: 16, padding: 16, marginTop: 8, marginBottom: 14 },
  challengeEyebrow: { color: colors.judge, fontSize: 10, fontWeight: "900", letterSpacing: 1.2 },
  challengeTitle: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: 6 },
  challengeHelp: { color: colors.muted, fontSize: 12, lineHeight: 19, marginTop: 7, marginBottom: 14 },
  challengeEmpty: { color: colors.muted, fontSize: 12, lineHeight: 18, fontStyle: "italic" },
  inputLabel: { color: colors.muted, fontSize: 9, fontWeight: "900", letterSpacing: 1, marginTop: 7, marginBottom: 6 },
  textArea: { minHeight: 78, backgroundColor: colors.background, borderColor: colors.line, borderWidth: 1, borderRadius: 11, color: colors.text, padding: 12, fontSize: 13, lineHeight: 19, textAlignVertical: "top" },
  validationText: { color: colors.warning, fontSize: 10, marginTop: 5 },
  challengeButton: { minHeight: 46, backgroundColor: colors.cyan, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 12, marginTop: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  challengeButtonText: { color: colors.background, fontSize: 13, fontWeight: "900" },
  cancelButton: { minHeight: 44, borderColor: colors.bear, borderWidth: 1, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 11, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 4 },
  cancelText: { color: colors.bear, fontSize: 13, fontWeight: "800" },
  disabledButton: { opacity: 0.42 },
  disclaimer: { color: colors.muted, fontSize: 10, lineHeight: 16, marginTop: 18 },
});
