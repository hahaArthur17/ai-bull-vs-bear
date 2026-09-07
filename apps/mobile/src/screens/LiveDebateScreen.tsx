import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  AccessibilityInfo,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

import { api, createDebateStreamClient } from "../api";
import {
  CanonicalDebateMessage,
  DraftDebateMessage,
} from "../components/debate/LiveDebateMessage";
import { debateActionStatus } from "../debateActionState";
import {
  debatePhaseBadge,
  getDebateChatLayout,
  shouldAnimateTranscriptScroll,
  shouldAutoFollowTranscript,
} from "../debateChatView";
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
import {
  createExplanationRequestGate,
  defaultExplanationQuestion,
  exactExplanationTerm,
} from "../explanationView";
import { colors as themeColors, interaction } from "../theme";
import type {
  DebateMessageRecord,
  DebateSessionDetail,
  ExplanationResult,
} from "../types";

type LiveDebateScreenProps = {
  ticker: string;
  initialDetail: DebateSessionDetail;
  onBack: () => void;
};

const colors = {
  background: themeColors.surface.canvas,
  surface: themeColors.surface.raised,
  elevated: themeColors.surface.elevated,
  line: themeColors.border.subtle,
  text: themeColors.content.primary,
  muted: themeColors.content.secondary,
  cyan: themeColors.agent.user,
  bull: themeColors.agent.bull,
  bear: themeColors.agent.bear,
  judge: themeColors.agent.judge,
  warning: themeColors.content.warning,
  danger: themeColors.content.danger,
} as const;

function newIdempotencyKey(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "pending";
}

function rolePresentation(
  role: DebateMessageRecord["message"]["role"] | DebateDraft["role"],
  isFinalJudge = false,
) {
  if (role === "bull") return { label: "BULL", color: colors.bull };
  if (role === "bear") return { label: "BEAR", color: colors.bear };
  if (role === "judge") {
    return {
      label: isFinalJudge ? "FINAL NEUTRAL JUDGE" : "INTERIM NEUTRAL JUDGE",
      color: colors.judge,
    };
  }
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
  const [explanationTarget, setExplanationTarget] = useState<DebateMessageRecord | null>(null);
  const [explanationTerm, setExplanationTerm] = useState("");
  const [explanationQuestion, setExplanationQuestion] = useState("");
  const [explanationResult, setExplanationResult] = useState<ExplanationResult | null>(null);
  const [explanationError, setExplanationError] = useState("");
  const [explaining, setExplaining] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const reduceMotionEnabled = useRef<boolean | null>(null);
  const challengeKey = useRef<string | null>(null);
  const explanationRequests = useRef(createExplanationRequestGate());
  const streamClient = useRef<DebateStreamClient | null>(null);
  const scrollRef = useRef<ScrollView | null>(null);
  const scrollFrame = useRef<number | null>(null);
  const followsTranscript = useRef(true);
  const { width: viewportWidth } = useWindowDimensions();
  const chatLayout = getDebateChatLayout(viewportWidth);
  const sessionId = initialDetail.session.id;

  const invalidateExplanationRequest = () => {
    explanationRequests.current.invalidate();
    setExplaining(false);
  };

  useEffect(() => {
    setSnapshot(createCanonicalDebateSnapshot(initialDetail));
    setConnectionError("");
    setActionError("");
    setChallengeTarget(null);
    setSelectedText("");
    setQuestion("");
    setExplanationTarget(null);
    setExplanationTerm("");
    setExplanationQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    setHasNewMessages(false);
    followsTranscript.current = true;
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
    }
    invalidateExplanationRequest();
    challengeKey.current = null;
  }, [sessionId]);

  useEffect(() => () => {
    explanationRequests.current.invalidate();
  }, []);

  useEffect(() => {
    let mounted = true;
    let preferenceEventReceived = false;
    const handleReduceMotionChanged = (enabled: boolean) => {
      preferenceEventReceived = true;
      if (mounted) reduceMotionEnabled.current = enabled;
    };
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      handleReduceMotionChanged,
    );

    void AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (mounted && !preferenceEventReceived) reduceMotionEnabled.current = enabled;
      })
      .catch(() => {
        // Keep the conservative no-animation default when this platform cannot report a preference.
      });

    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

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

  useEffect(() => {
    if (snapshot.lastSequence === 0) return;
    if (!followsTranscript.current) {
      setHasNewMessages(true);
      return;
    }
    scheduleTranscriptFollow(true);
  }, [snapshot.canonicalMessages.length, snapshot.lastSequence]);

  useEffect(() => () => {
    if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
  }, []);

  const status = debateStatusCopy(snapshot);
  const drafts = Object.values(snapshot.drafts);
  const activeRoundNumber = snapshot.sessionStatus === "queued_round_2"
    || snapshot.sessionStatus === "running_round_2"
    ? 2
    : 1;
  const canCancel = canCancelDebate(snapshot) && !cancelling;
  const canChallenge = canChallengeDebate(snapshot);
  const selectedTextIsValid = challengeTarget !== null
    && selectedText.trim().length > 0
    && challengeTarget.message.content.includes(selectedText.trim());
  const canSubmitChallenge = canChallenge
    && selectedTextIsValid
    && question.trim().length > 0
    && !challenging;
  const selectedExplanationTerm = explanationTarget
    ? exactExplanationTerm(explanationTarget, explanationTerm)
    : null;
  const canSubmitExplanation = selectedExplanationTerm !== null
    && explanationQuestion.trim().length > 0
    && !explaining;
  const activeAction = debateActionStatus({ cancelling, challenging, explaining });

  const updateTranscriptFollow = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
    const shouldFollow = shouldAutoFollowTranscript(
      contentSize.height,
      layoutMeasurement.height,
      contentOffset.y,
    );
    followsTranscript.current = shouldFollow;
    if (shouldFollow) setHasNewMessages(false);
  };

  const followLatestMessage = () => {
    followsTranscript.current = true;
    setHasNewMessages(false);
    scrollRef.current?.scrollToEnd({
      animated: shouldAnimateTranscriptScroll(reduceMotionEnabled.current),
    });
  };

  function scheduleTranscriptFollow(animated: boolean) {
    if (scrollFrame.current !== null) return;
    scrollFrame.current = requestAnimationFrame(() => {
      scrollFrame.current = null;
      if (followsTranscript.current) {
        scrollRef.current?.scrollToEnd({
          animated: animated && shouldAnimateTranscriptScroll(reduceMotionEnabled.current),
        });
      }
    });
  }

  const selectChallengeTarget = (record: DebateMessageRecord) => {
    setChallengeTarget(record);
    setSelectedText(record.message.content.slice(0, 500));
    setActionError("");
    challengeKey.current = null;
  };

  const selectExplanationTerm = (record: DebateMessageRecord, term: string) => {
    const selectedTerm = exactExplanationTerm(record, term);
    if (selectedTerm === null) {
      setActionError("This term is not an exact selection from a complete message.");
      return;
    }
    invalidateExplanationRequest();
    setExplanationTarget(record);
    setExplanationTerm(selectedTerm);
    setExplanationQuestion(defaultExplanationQuestion(selectedTerm));
    setExplanationResult(null);
    setExplanationError("");
  };

  const closeExplanation = () => {
    invalidateExplanationRequest();
    setExplanationTarget(null);
    setExplanationTerm("");
    setExplanationQuestion("");
    setExplanationResult(null);
    setExplanationError("");
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

  const submitExplanation = async () => {
    if (!explanationTarget || !selectedExplanationTerm || !canSubmitExplanation) return;
    const requestId = explanationRequests.current.start();
    setExplaining(true);
    setExplanationError("");
    try {
      const result = await api.explainDebate(sessionId, {
        messageId: explanationTarget.message.id,
        selectedText: selectedExplanationTerm,
        question: explanationQuestion.trim(),
      });
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplanationResult(result);
      }
    } catch (error) {
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplanationError(
          error instanceof Error ? error.message : "Could not explain this term.",
        );
      }
    } finally {
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplaining(false);
      }
    }
  };

  const statusPanel = (
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

  const cancelControl = canCancel || cancelling ? (
    <Pressable
      disabled={!canCancel}
      style={[screenStyles.cancelButton, !canCancel && screenStyles.disabledButton]}
      onPress={() => void cancelDebate()}
      accessibilityLabel="Stop the current Debate generation"
      accessibilityRole="button"
      accessibilityState={{ busy: cancelling, disabled: !canCancel }}
    >
      {cancelling ? <ActivityIndicator color={colors.bear} size="small" /> : null}
      <Text style={screenStyles.cancelText}>
        {cancelling ? "Requesting cancellation…" : "Stop this generation"}
      </Text>
    </Pressable>
  ) : null;

  return (
    <View style={screenStyles.screen}>
    <ScrollView
      ref={scrollRef}
      style={screenStyles.scroll}
      contentContainerStyle={[
        screenStyles.page,
        { paddingHorizontal: chatLayout.pagePadding },
      ]}
      onScroll={updateTranscriptFollow}
      onContentSizeChange={() => {
        if (followsTranscript.current) scheduleTranscriptFollow(false);
      }}
      scrollEventThrottle={32}
      accessibilityLabel={`${ticker} live Bull versus Bear Debate`}
    >
      <Pressable
        onPress={onBack}
        style={screenStyles.backButton}
        accessibilityLabel={`Return to ${ticker} market snapshot`}
        accessibilityRole="button"
      >
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
          <Text style={screenStyles.liveText}>
            {debatePhaseBadge(snapshot.sessionStatus, snapshot.status)}
          </Text>
        </View>
      </View>

      <View style={[screenStyles.workspace, chatLayout.showStatusRail && screenStyles.workspaceDesktop]}>
        <View style={screenStyles.conversationColumn}>
      {!chatLayout.showStatusRail ? statusPanel : null}

      {connectionError ? (
        <View style={screenStyles.warningCard}>
          <Text style={screenStyles.warningText}>{connectionError}</Text>
          <Pressable
            style={screenStyles.inlineButton}
            onPress={() => setStreamEpoch((current) => current + 1)}
            accessibilityLabel="Reconnect to live Debate updates"
            accessibilityRole="button"
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

      {activeAction ? (
        <View accessibilityLiveRegion="polite" style={screenStyles.actionStatusCard}>
          <Text style={screenStyles.actionStatusLabel}>{activeAction.label}</Text>
          <Text style={screenStyles.actionStatusDetail}>{activeAction.detail}</Text>
        </View>
      ) : null}

      <View style={screenStyles.sectionHeader}>
        <Text style={screenStyles.sectionTitle}>Debate transcript</Text>
        <Text style={screenStyles.sectionMeta}>
          {snapshot.canonicalMessages.length} canonical · {drafts.length} draft
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

      <View style={screenStyles.transcript}>
      {snapshot.canonicalMessages.map((record) => (
        <CanonicalDebateMessage
          key={record.message.id}
          record={record}
          bubbleWidth={chatLayout.bubbleWidth}
          judgeWidth={chatLayout.judgeWidth}
          challengeEnabled={canChallenge}
          selected={challengeTarget?.message.id === record.message.id}
          onChallenge={() => selectChallengeTarget(record)}
          onExplainTerm={(term) => selectExplanationTerm(record, term)}
        />
      ))}

      {drafts.map((draft) => (
        <DraftDebateMessage
          key={draft.messageId}
          draft={draft}
          roundNumber={activeRoundNumber}
          bubbleWidth={chatLayout.bubbleWidth}
          judgeWidth={chatLayout.judgeWidth}
        />
      ))}
      </View>

      {explanationTarget ? (
        <View style={screenStyles.explanationPanel}>
          <View style={screenStyles.rowBetween}>
            <Text style={screenStyles.explanationEyebrow}>TERM EXPLANATION · READ ONLY</Text>
            <Pressable
              onPress={closeExplanation}
              style={screenStyles.dismissButton}
              accessibilityRole="button"
              accessibilityLabel="Close term explanation"
            >
              <Text style={screenStyles.dismissButtonText}>Close</Text>
            </Pressable>
          </View>
          <Text style={screenStyles.explanationTitle}>Understand the argument</Text>
          <Text style={screenStyles.explanationHelp}>
            This explains the selected term using only this complete message and its linked,
            dated evidence. It does not change the Debate or start another round.
          </Text>
          <Text style={screenStyles.inputLabel}>EXACT TERM · {rolePresentation(explanationTarget.message.role).label}</Text>
          <Text style={screenStyles.selectedTerm}>{selectedExplanationTerm || explanationTerm}</Text>
          <Text style={screenStyles.inputLabel}>YOUR QUESTION</Text>
          <TextInput
            value={explanationQuestion}
            onChangeText={(value) => {
              invalidateExplanationRequest();
              setExplanationQuestion(value);
              setExplanationResult(null);
            }}
            maxLength={500}
            multiline
            style={screenStyles.textArea}
            placeholder="What does this mean in the argument?"
            placeholderTextColor={colors.muted}
            accessibilityLabel="Question about the selected term"
            accessibilityHint="Ask for a read-only explanation of the selected term."
          />
          {explanationError ? (
            <Text style={screenStyles.validationText}>{explanationError}</Text>
          ) : null}
          <Pressable
            disabled={!canSubmitExplanation}
            style={[
              screenStyles.explanationButton,
              !canSubmitExplanation && screenStyles.disabledButton,
            ]}
            onPress={() => void submitExplanation()}
            accessibilityLabel="Explain the selected term"
            accessibilityRole="button"
            accessibilityState={{ busy: explaining, disabled: !canSubmitExplanation }}
          >
            {explaining ? <ActivityIndicator color={colors.background} size="small" /> : null}
            <Text style={screenStyles.explanationButtonText}>
              {explaining ? "Explaining term…" : "Explain this term"}
            </Text>
          </Pressable>
          {explanationResult ? (
            <View style={screenStyles.explanationResult}>
              <Text style={screenStyles.explanationResultTitle}>Explanation</Text>
              <Text style={screenStyles.explanationContent}>{explanationResult.content}</Text>
              {explanationResult.evidence_ids.length > 0 ? (
                <Text style={screenStyles.citations}>
                  EVIDENCE {explanationResult.evidence_ids.join(" · ")}
                </Text>
              ) : null}
              {explanationResult.guardrail_status === "rewritten" ? (
                <Text style={screenStyles.explanationSafetyNote}>
                  Safety language was adjusted to keep this educational.
                </Text>
              ) : null}
            </View>
          ) : null}
        </View>
      ) : null}

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
                accessibilityLabel="Exact quoted passage for the Round 2 challenge"
                accessibilityHint="Enter text copied exactly from the selected Debate message."
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
                accessibilityLabel="Question for the Round 2 challenge"
              />
              <Pressable
                disabled={!canSubmitChallenge}
                style={[
                  screenStyles.challengeButton,
                  !canSubmitChallenge && screenStyles.disabledButton,
                ]}
                onPress={() => void submitChallenge()}
                accessibilityLabel="Queue Round 2 challenge"
                accessibilityRole="button"
                accessibilityState={{ busy: challenging, disabled: !canSubmitChallenge }}
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

      {!chatLayout.showStatusRail ? cancelControl : null}

        </View>
        {chatLayout.showStatusRail ? (
          <View style={screenStyles.statusRail}>
            {statusPanel}
            {connectionError ? (
              <Text style={screenStyles.railNote}>Connection controls remain available in the transcript.</Text>
            ) : null}
            {cancelControl}
          </View>
        ) : null}
      </View>

      <Text style={screenStyles.disclaimer}>
        Educational analysis only. Bull and Bear arguments are evidence-grounded scenarios, not
        trading instructions or predictions.
      </Text>
    </ScrollView>
    {hasNewMessages ? (
      <View
        accessibilityLiveRegion="polite"
        pointerEvents="box-none"
        style={screenStyles.newMessagesOverlay}
      >
        <Pressable
          onPress={followLatestMessage}
          style={screenStyles.newMessagesButton}
          accessibilityLabel="Jump to new Debate messages"
          accessibilityRole="button"
        >
          <Text style={screenStyles.newMessagesText}>New messages ↓</Text>
        </Pressable>
      </View>
    ) : null}
    </View>
  );
}

const screenStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1, backgroundColor: colors.background },
  page: { alignSelf: "center", width: "100%", maxWidth: 1160, backgroundColor: colors.background, padding: 20, paddingBottom: 130 },
  workspace: { width: "100%" },
  workspaceDesktop: { flexDirection: "row", alignItems: "flex-start", gap: 24 },
  conversationColumn: { flex: 1, minWidth: 0 },
  transcript: { width: "100%" },
  statusRail: { width: 300 },
  railNote: { color: colors.muted, fontSize: 10, lineHeight: 16, marginBottom: 10 },
  backButton: { alignSelf: "flex-start", justifyContent: "center", marginBottom: 16, minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 4 },
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
  warningCard: { backgroundColor: themeColors.surface.warning, borderColor: themeColors.border.warning, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 12 },
  warningText: { color: colors.warning, fontSize: 12, lineHeight: 18 },
  inlineButton: { alignSelf: "flex-start", alignItems: "center", borderBottomColor: colors.warning, borderBottomWidth: 1, justifyContent: "center", marginTop: 8, minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 4 },
  inlineButtonText: { color: colors.warning, fontSize: 12, fontWeight: "800" },
  errorCard: { backgroundColor: themeColors.surface.danger, borderColor: themeColors.border.danger, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 12 },
  errorText: { color: colors.danger, fontSize: 12, lineHeight: 18 },
  actionStatusCard: { backgroundColor: colors.elevated, borderColor: colors.line, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 12 },
  actionStatusLabel: { color: colors.cyan, fontSize: 12, fontWeight: "900" },
  actionStatusDetail: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 4 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", gap: 10, marginTop: 8, marginBottom: 12 },
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  sectionMeta: { color: colors.muted, fontSize: 10 },
  emptyCard: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderStyle: "dashed", borderRadius: 14, padding: 18, marginBottom: 12 },
  emptyTitle: { color: colors.text, fontSize: 14, fontWeight: "800", marginBottom: 7 },
  emptyText: { color: colors.muted, fontSize: 12, lineHeight: 19 },
  citations: { color: colors.cyan, fontSize: 9, lineHeight: 15, fontWeight: "700", marginTop: 12 },
  explanationPanel: { backgroundColor: themeColors.surface.positive, borderColor: colors.bull, borderWidth: 1, borderRadius: 16, padding: 16, marginTop: 8, marginBottom: 14 },
  explanationEyebrow: { color: colors.bull, fontSize: 10, fontWeight: "900", letterSpacing: 1.2 },
  explanationTitle: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: 6 },
  explanationHelp: { color: colors.muted, fontSize: 12, lineHeight: 19, marginTop: 7, marginBottom: 7 },
  dismissButton: { alignItems: "center", borderBottomColor: colors.muted, borderBottomWidth: 1, justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 4 },
  dismissButtonText: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  selectedTerm: { color: colors.bull, backgroundColor: colors.background, borderColor: colors.line, borderWidth: 1, borderRadius: 10, paddingHorizontal: 11, paddingVertical: 9, fontSize: 13, fontWeight: "800" },
  explanationButton: { minHeight: 46, backgroundColor: colors.bull, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 12, marginTop: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  explanationButtonText: { color: colors.background, fontSize: 13, fontWeight: "900" },
  explanationResult: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 11, padding: 13, marginTop: 14 },
  explanationResultTitle: { color: colors.bull, fontSize: 11, fontWeight: "900", letterSpacing: 0.8 },
  explanationContent: { color: colors.text, fontSize: 13, lineHeight: 20, marginTop: 8 },
  explanationSafetyNote: { color: colors.warning, fontSize: 10, lineHeight: 16, marginTop: 10 },
  challengePanel: { backgroundColor: themeColors.surface.information, borderColor: colors.judge, borderWidth: 1, borderRadius: 16, padding: 16, marginTop: 8, marginBottom: 14 },
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
  newMessagesOverlay: { position: "absolute", left: 0, right: 0, bottom: 92, alignItems: "center" },
  newMessagesButton: { minHeight: interaction.minTargetSize, justifyContent: "center", backgroundColor: themeColors.action.primary, borderColor: themeColors.border.inverse, borderWidth: 1, borderRadius: 22, paddingHorizontal: 18, elevation: 8, boxShadow: "0px 8px 20px rgba(0,0,0,0.32)" },
  newMessagesText: { color: themeColors.content.onSignal, fontSize: 12, fontWeight: "900" },
  disclaimer: { color: colors.muted, fontSize: 10, lineHeight: 16, marginTop: 18 },
});
