import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  AccessibilityInfo,
  AppState,
  KeyboardAvoidingView,
  Modal,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableWithoutFeedback,
  useWindowDimensions,
  View,
} from "react-native";

import { createPendingInterruption, savePendingInterruption, loadPendingInterruption,
  confirmPendingInterruption, type PendingInterruption } from "../pendingInterruption";
import { api, createDebateStreamClient } from "../api";
import { FocusablePressable } from "../components/common";
import {
  CanonicalDebateMessage,
  DraftDebateMessage,
} from "../components/debate/LiveDebateMessage";
import {
  InterruptionComposer,
  type InterruptionComposerBusy,
} from "../components/debate/InterruptionComposer";
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
import { REVEAL_CADENCE_MS, RevealScheduler } from "../revealScheduler";
import {
  canCancelDebate,
  canChallengeDebate,
  debateStatusCopy,
} from "../liveDebateView";
import {
  activeInterruptionDraft,
  canStopBeforeOutput,
  canStopVisibleDraft,
  findInterruptedMessage,
  findInterjection,
  interruptionIdempotencyKey,
  isInterruptionJobPending,
  shouldReconnectAfterInterruptionEnd,
  shouldStopBeforeOutput,
} from "../interruptionState";
import {
  canDismissPointInquiry,
  canPrepareRoundTwoChallenge,
  canSubmitRoundTwoChallenge,
  INITIAL_POINT_INQUIRY_MODE,
} from "../pointInquiryView";
import type { PointInquiryMode } from "../pointInquiryView";
import {
  createExplanationRequestGate,
  defaultExplanationQuestion,
  defaultPointPassage,
  exactExplanationTerm,
} from "../explanationView";
import { colors as themeColors, interaction } from "../theme";
import type {
  DebateMessageRecord,
  DebateSessionDetail,
  ExplanationResult,
} from "../types";

type LiveDebateScreenProps = {
  accountId: string;
  ticker: string;
  initialDetail: DebateSessionDetail;
  onBack: () => void;
};

const interruptionsEnabled = process.env.EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED === "true";

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
  accountId,
  onBack,
}: LiveDebateScreenProps) {
  const [snapshot, setSnapshot] = useState<DebateStreamSnapshot>(() =>
    createCanonicalDebateSnapshot(initialDetail),
  );
  const [recoveryReady, setRecoveryReady] = useState(!interruptionsEnabled);
  const [streamEpoch, setStreamEpoch] = useState(0);
  const [connectionError, setConnectionError] = useState("");
  const [actionError, setActionError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [challenging, setChallenging] = useState(false);
  const [pointTarget, setPointTarget] = useState<DebateMessageRecord | null>(null);
  const [pointDialogMode, setPointDialogMode] = useState<PointInquiryMode>(INITIAL_POINT_INQUIRY_MODE);
  const [selectedText, setSelectedText] = useState("");
  const [question, setQuestion] = useState("");
  const [explanationResult, setExplanationResult] = useState<ExplanationResult | null>(null);
  const [explanationError, setExplanationError] = useState("");
  const [explaining, setExplaining] = useState(false);
  const [interjection, setInterjection] = useState("");
  const [interjectionSaved, setInterjectionSaved] = useState(false);
  const [interruptionBusy, setInterruptionBusy] = useState<InterruptionComposerBusy>(null);
  const [interruptionError, setInterruptionError] = useState("");
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const [, setRevealVersion] = useState(0);
  const reduceMotionEnabled = useRef<boolean | null>(null);
  const screenReaderEnabled = useRef<boolean | null>(null);
  const appIsActive = useRef(AppState.currentState === "active");
  const revealScheduler = useRef(new RevealScheduler());
  const pendingInterruption = useRef<PendingInterruption | null>(null);
  const challengeKey = useRef<string | null>(null);
  const interjectionKey = useRef<{ identity: string; key: string } | null>(null);
  const continuationKey = useRef<{ identity: string; key: string } | null>(null);
  const interruptionHydration = useRef<string | null>(null);
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
    setPointTarget(null);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText("");
    setQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    setInterjection("");
    setInterjectionSaved(false);
    setInterruptionBusy(null);
    setInterruptionError("");
    setHasNewMessages(false);
    revealScheduler.current = new RevealScheduler();
    pendingInterruption.current = null;
    followsTranscript.current = true;
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
    }
    invalidateExplanationRequest();
    challengeKey.current = null;
    interjectionKey.current = null;
    continuationKey.current = null;
    interruptionHydration.current = null;
  }, [sessionId]);

  useEffect(() => {
    if (!interruptionsEnabled) return;
    let active = true;
    setRecoveryReady(false);
    void loadPendingInterruption(AsyncStorage, accountId, sessionId).then(async (pending) => {
      if (!active) return;
      if (pending) {
        const saved = initialDetail.messages.find((record) => record.message.id === pending.messageId);
        if (saved && !saved.message.is_complete && saved.message.generation_id === pending.generationId
            && saved.message.content === pending.visiblePrefix) {
          await confirmPendingInterruption(AsyncStorage, accountId, sessionId, pending.idempotencyKey);
          if (!active) return;
        } else {
          pendingInterruption.current = pending;
          const visibleIds = new Set(pending.precedingMessageIds);
          revealScheduler.current.freeze({
            canonicalMessages: initialDetail.messages.filter((record) => visibleIds.has(record.message.id)),
            drafts: [{ messageId: pending.messageId, generationId: pending.generationId,
              role: pending.role, content: pending.visiblePrefix, citations: [], nextDeltaIndex: 0 }],
            activeMessageId: pending.messageId,
          });
          setActionError("A previous Stop is not confirmed. Text stays frozen; retry Stop here.");
        }
      }
      setRecoveryReady(true);
    }).catch(() => {
      if (active) setActionError("Could not check the saved Stop request. Reopen this Debate to retry safely.");
    });
    return () => { active = false; };
  }, [accountId, sessionId]);

  useEffect(() => () => {
    explanationRequests.current.invalidate();
  }, []);

  useEffect(() => {
    let mounted = true;
    let preferenceEventReceived = false;
    const handleReduceMotionChanged = (enabled: boolean) => {
      preferenceEventReceived = true;
      reduceMotionEnabled.current = enabled;
      if (enabled) revealScheduler.current.settleAll();
      if (mounted) setRevealVersion((version) => version + 1);
    };
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      handleReduceMotionChanged,
    );

    void AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (!preferenceEventReceived) handleReduceMotionChanged(enabled);
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
    const applyScreenReader = (enabled: boolean) => {
      screenReaderEnabled.current = enabled;
      if (enabled) {
        revealScheduler.current.settleAll();
        if (mounted) setRevealVersion((version) => version + 1);
      }
    };
    const subscription = AccessibilityInfo.addEventListener("screenReaderChanged", applyScreenReader);
    void AccessibilityInfo.isScreenReaderEnabled().then(applyScreenReader).catch(() => {
      // The visible scheduler remains usable when this native preference is unavailable.
    });
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasActive = appIsActive.current;
      appIsActive.current = nextState === "active";
      if (!appIsActive.current) {
        revealScheduler.current.settleAll();
        setRevealVersion((version) => version + 1);
      } else if (!wasActive) {
        // Native backgrounding can tear down XHR without delivering an error.
        // A fresh client reloads canonical state before resuming SSE.
        setStreamEpoch((current) => current + 1);
      }
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    if (!recoveryReady) return;
    revealScheduler.current.sync(snapshot.canonicalMessages, snapshot.drafts, {
      immediate: reduceMotionEnabled.current === true
        || screenReaderEnabled.current === true
        || !appIsActive.current
        || snapshot.status === "reconnecting",
    });
    setRevealVersion((version) => version + 1);
  }, [snapshot, recoveryReady]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (reduceMotionEnabled.current === true || screenReaderEnabled.current === true || !appIsActive.current) return;
      if (revealScheduler.current.advance()) setRevealVersion((version) => version + 1);
    }, REVEAL_CADENCE_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!recoveryReady || pendingInterruption.current) return;
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
  }, [sessionId, streamEpoch, recoveryReady]);

  useEffect(() => {
    if (!interruptionsEnabled
      || !recoveryReady
      || snapshot.sessionStatus !== "interrupted_awaiting_user"
      || !isInterruptionJobPending(snapshot.jobStatus)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const schedule = (delay: number) => {
      timer = setTimeout(() => { void poll(); }, delay);
    };
    const poll = async () => {
      try {
        const detail = await api.getDebate(sessionId);
        if (!active) return;
        setSnapshot((current) => createCanonicalDebateSnapshot(
          detail,
          current.lastSequence,
          current.status,
        ));
        const serverJobPending = detail.session.status === "interrupted_awaiting_user"
          && (detail.job?.status === "queued" || detail.job?.status === "running");
        if (serverJobPending) schedule(500);
      } catch {
        if (active) schedule(1000);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer !== null) clearTimeout(timer);
    };
  }, [recoveryReady, sessionId, snapshot.jobStatus, snapshot.sessionStatus]);

  useEffect(() => {
    const target = findInterruptedMessage(snapshot.canonicalMessages);
    if (snapshot.sessionStatus !== "interrupted_awaiting_user" || !target) {
      interruptionHydration.current = null;
      if (interruptionBusy === null) {
        setInterjection("");
        setInterjectionSaved(false);
      }
      return;
    }
    const identity = `${sessionId}:${target.message.id}:${snapshot.activeGenerationId || ""}`;
    if (interruptionHydration.current === identity) return;
    interruptionHydration.current = identity;
    const saved = findInterjection(
      snapshot.canonicalMessages,
      target.message.id,
      snapshot.activeGenerationId || "",
    );
    if (saved) {
      setInterjection(saved.message.content);
      setInterjectionSaved(true);
    } else {
      setInterjection("");
      setInterjectionSaved(false);
    }
  }, [
    interruptionBusy,
    sessionId,
    snapshot.activeGenerationId,
    snapshot.canonicalMessages,
    snapshot.sessionStatus,
  ]);

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
  const revealDisplay = recoveryReady ? revealScheduler.current.display()
    : { canonicalMessages: [], drafts: [], activeMessageId: null };
  const interruptionPoint = findInterruptedMessage(snapshot.canonicalMessages);
  const savedInterjection = interruptionPoint
    ? findInterjection(
      snapshot.canonicalMessages,
      interruptionPoint.message.id,
      snapshot.activeGenerationId || "",
    )
    : null;
  const interruptionConfirmed = interruptionsEnabled
    && recoveryReady
    && pendingInterruption.current === null
    && snapshot.sessionStatus === "interrupted_awaiting_user"
    && snapshot.activeGenerationId !== null
    && interruptionPoint !== null;
  const interruptionJobSettled = !isInterruptionJobPending(snapshot.jobStatus);
  const canExplainStoppedText = interruptionPoint !== null
    && exactExplanationTerm(
      interruptionPoint,
      defaultPointPassage(interruptionPoint.message.content),
    ) !== null;
  const drafts = revealDisplay.drafts;
  const activeRoundNumber = snapshot.sessionStatus === "queued_round_2"
    || snapshot.sessionStatus === "running_round_2"
    ? 2
    : 1;
  const canCancel = (interruptionsEnabled
    ? Boolean(
      pendingInterruption.current
      || canStopVisibleDraft(snapshot, drafts[0])
      || canStopBeforeOutput(snapshot),
    )
    : canCancelDebate(snapshot)) && !cancelling;
  const canChallenge = !pendingInterruption.current && canChallengeDebate(snapshot);
  const selectedTextIsValid = pointTarget !== null
    && selectedText.trim().length > 0
    && pointTarget.message.content.includes(selectedText.trim());
  const canSubmitChallenge = canSubmitRoundTwoChallenge({
    mode: pointDialogMode,
    canChallenge,
    selectedTextIsValid,
    question,
    challenging,
  });
  const selectedExplanationTerm = pointTarget
    ? exactExplanationTerm(pointTarget, selectedText)
    : null;
  const canSubmitExplanation = selectedExplanationTerm !== null
    && question.trim().length > 0
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

  const openPointQuestion = (record: DebateMessageRecord) => {
    invalidateExplanationRequest();
    setPointTarget(record);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText(defaultPointPassage(record.message.content));
    setQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    setActionError("");
    challengeKey.current = null;
  };

  const selectExplanationTerm = (record: DebateMessageRecord, term: string) => {
    const selectedTerm = exactExplanationTerm(record, term);
    if (selectedTerm === null) {
      setActionError("This term is not an exact selection from an explainable message.");
      return;
    }
    invalidateExplanationRequest();
    setPointTarget(record);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText(selectedTerm);
    setQuestion(defaultExplanationQuestion(selectedTerm));
    setExplanationResult(null);
    setExplanationError("");
  };

  const closePointDialog = () => {
    invalidateExplanationRequest();
    setPointTarget(null);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText("");
    setQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    challengeKey.current = null;
  };

  const prepareRoundTwoChallenge = () => {
    invalidateExplanationRequest();
    setPointDialogMode("challenge");
    setExplanationError("");
    setActionError("");
  };

  const returnToExplanation = () => {
    setPointDialogMode("explain");
    challengeKey.current = null;
  };

  const cancelDebate = async () => {
    if (!snapshot.activeGenerationId || !canCancel) return;
    setCancelling(true);
    setActionError("");
    try {
      let detail: DebateSessionDetail;
      if (interruptionsEnabled) {
        const visible = drafts[0];
        if (!pendingInterruption.current && !visible && !canStopBeforeOutput(snapshot)) return;
        revealScheduler.current.freeze(revealDisplay);
        streamClient.current?.stop();
        const pending = pendingInterruption.current;
        const providerDraft = activeInterruptionDraft(snapshot, visible);
        const beforeOutput = pending
          ? pending.messageId === pending.generationId
          : shouldStopBeforeOutput(snapshot, visible);
        const generationId = pending?.generationId
          || providerDraft?.generationId
          || snapshot.activeGenerationId;
        const draftRole = providerDraft?.role || visible?.role;
        const target = pending || createPendingInterruption({
          accountId,
          sessionId,
          generationId,
          // The before-output endpoint creates its stable empty anchor with
          // the generation ID. A visible draft already has a message ID.
          messageId: beforeOutput ? generationId : providerDraft!.messageId,
          visiblePrefix: beforeOutput ? "" : visible?.content || "",
          role: draftRole === "bull" || draftRole === "bear" || draftRole === "judge"
            ? draftRole
            : "system",
          precedingMessageIds: revealDisplay.canonicalMessages.map((record) => record.message.id),
        });
        pendingInterruption.current = target;
        setRevealVersion((version) => version + 1);
        await savePendingInterruption(AsyncStorage, target);
        detail = beforeOutput
          ? await api.interruptBeforeOutputDebate(sessionId, target.generationId)
          : await api.interruptDebate(sessionId, {
            generationId: target.generationId,
            messageId: target.messageId,
            content: target.visiblePrefix,
          });
        const saved = detail.messages.find((record) => record.message.id === target.messageId);
        if (!saved || saved.message.is_complete || saved.message.generation_id !== target.generationId
            || saved.message.content !== target.visiblePrefix) {
          throw new Error("Stop was not confirmed. Text remains frozen; retry Stop here.");
        }
        await confirmPendingInterruption(AsyncStorage, accountId, sessionId, target.idempotencyKey);
        pendingInterruption.current = null;
        revealScheduler.current.releaseFreeze();
        revealScheduler.current.sync(detail.messages, {}, { immediate: true });
      } else {
        detail = await api.cancelDebate(sessionId, snapshot.activeGenerationId);
      }
      setSnapshot((current) => createCanonicalDebateSnapshot(
        detail,
        current.lastSequence,
        current.status,
      ));
    } catch (error) {
      setActionError(interruptionsEnabled
        ? "Stop was not confirmed. Text remains frozen; retry Stop here."
        : error instanceof Error ? error.message : "Could not cancel this Debate.");
    } finally {
      setCancelling(false);
    }
  };

  const saveInterjection = async () => {
    if (!interruptionConfirmed || !interruptionPoint || interruptionBusy !== null) return;
    const waitingGenerationId = snapshot.activeGenerationId;
    if (!waitingGenerationId) return;
    const content = interjection.trim();
    if (!content) return;
    // Include the post-Stop generation so a repeated interruption at the same
    // frozen message cannot reuse the prior generation's message identifier.
    const identity = `${waitingGenerationId}:${interruptionPoint.message.generation_id}:${interruptionPoint.message.id}:${content}`;
    if (interjectionKey.current?.identity !== identity) {
      interjectionKey.current = { identity, key: interruptionIdempotencyKey("interject", identity) };
    }
    const key = interjectionKey.current.key;
    setInterruptionBusy("save");
    setInterruptionError("");
    try {
      const detail = await api.interjectDebate(sessionId, {
        generationId: waitingGenerationId,
        content,
        idempotencyKey: key,
      });
      const saved = findInterjection(
        detail.messages,
        interruptionPoint.message.id,
        waitingGenerationId,
      );
      if (!saved) throw new Error("The viewpoint was not confirmed. Retry save.");
      setSnapshot(createCanonicalDebateSnapshot(detail));
      setInterjection(saved.message.content);
      setInterjectionSaved(true);
    } catch (error) {
      setInterjectionSaved(false);
      setInterruptionError(error instanceof Error ? error.message : "Could not save your viewpoint.");
    } finally {
      setInterruptionBusy(null);
    }
  };

  const continueInterruptedDebate = async () => {
    if (!interruptionConfirmed
      || !interruptionPoint
      || !savedInterjection
      || !interruptionJobSettled
      || interruptionBusy !== null) return;
    const waitingGenerationId = snapshot.activeGenerationId;
    if (!waitingGenerationId) return;
    // Continue job identifiers are scoped to the waiting generation. A later
    // stop at the same frozen point needs a fresh job key while retries for
    // this request keep the same key.
    const identity = `${waitingGenerationId}:${interruptionPoint.message.generation_id}:${savedInterjection.message.id}`;
    if (continuationKey.current?.identity !== identity) {
      continuationKey.current = { identity, key: interruptionIdempotencyKey("continue", identity) };
    }
    const key = continuationKey.current.key;
    setInterruptionBusy("continue");
    setInterruptionError("");
    try {
      const detail = await api.continueInterruptedDebate(sessionId, {
        generationId: waitingGenerationId,
        interjectionId: savedInterjection.message.id,
        idempotencyKey: key,
      });
      setSnapshot(createCanonicalDebateSnapshot(detail));
      setStreamEpoch((current) => current + 1);
    } catch (error) {
      setInterruptionError(error instanceof Error ? error.message : "Could not continue the Debate.");
    } finally {
      setInterruptionBusy(null);
    }
  };

  const endInterruptedDebate = async () => {
    if (!interruptionConfirmed || !interruptionPoint || interruptionBusy !== null) return;
    setInterruptionBusy("end");
    setInterruptionError("");
    try {
      const detail = await api.endInterruptedDebate(sessionId, interruptionPoint.message.id);
      streamClient.current?.stop();
      setSnapshot(createCanonicalDebateSnapshot(detail));
      // End can return cancel_requested while a running Worker settles. The
      // interruption screen has no active stream after Stop, so reconnect to
      // observe the durable session.cancelled event instead of leaving the
      // user on a permanent "Cancelling" state.
      if (shouldReconnectAfterInterruptionEnd(detail.session.status)) {
        setStreamEpoch((current) => current + 1);
      }
    } catch (error) {
      setInterruptionError(error instanceof Error ? error.message : "Could not end the Debate.");
    } finally {
      setInterruptionBusy(null);
    }
  };

  const submitChallenge = async () => {
    if (!pointTarget || !canSubmitChallenge) return;
    setChallenging(true);
    setActionError("");
    challengeKey.current ||= newIdempotencyKey("round2");
    try {
      const detail = await api.challengeDebate(sessionId, {
        selectedMessageId: pointTarget.message.id,
        selectedText: selectedText.trim(),
        question: question.trim(),
        idempotencyKey: challengeKey.current,
      });
      setSnapshot(createCanonicalDebateSnapshot(detail));
      closePointDialog();
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
    if (!pointTarget || !selectedExplanationTerm || !canSubmitExplanation) return;
    const requestId = explanationRequests.current.start();
    setExplaining(true);
    setExplanationError("");
    try {
      const result = await api.explainDebate(sessionId, {
        messageId: pointTarget.message.id,
        selectedText: selectedExplanationTerm,
        question: question.trim(),
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
    <FocusablePressable
      disabled={!canCancel}
      style={[screenStyles.cancelButton, !canCancel && screenStyles.disabledButton]}
      onPress={() => void cancelDebate()}
      accessibilityLabel="Stop the current Debate generation"
      accessibilityRole="button"
      accessibilityState={{ busy: cancelling, disabled: !canCancel }}
    >
      {cancelling ? <ActivityIndicator color={colors.bear} size="small" /> : null}
      <Text style={screenStyles.cancelText}>
        {cancelling ? "Confirming stop…" : interruptionsEnabled ? "Stop here" : "Stop this generation"}
      </Text>
    </FocusablePressable>
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
      <FocusablePressable
        onPress={onBack}
        style={screenStyles.backButton}
        accessibilityLabel={`Return to ${ticker} market snapshot`}
        accessibilityRole="button"
      >
        <Text style={screenStyles.backText}>← Market snapshot</Text>
      </FocusablePressable>

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
          <FocusablePressable
            style={screenStyles.inlineButton}
            onPress={() => setStreamEpoch((current) => current + 1)}
            accessibilityLabel="Reconnect to live Debate updates"
            accessibilityRole="button"
          >
            <Text style={screenStyles.inlineButtonText}>Reconnect</Text>
          </FocusablePressable>
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
          {revealDisplay.canonicalMessages.length} canonical · {drafts.length} draft
        </Text>
      </View>

      {revealDisplay.canonicalMessages.length === 0 && drafts.length === 0 ? (
        <View style={screenStyles.emptyCard}>
          <Text style={screenStyles.emptyTitle}>The transcript is intentionally empty</Text>
          <Text style={screenStyles.emptyText}>
            Queue admission returned before generation. Messages will appear here only after a
            Worker starts; partial output stays visually distinct from durable output.
          </Text>
        </View>
      ) : null}

      <View style={screenStyles.transcript}>
      {revealDisplay.canonicalMessages.map((record) => (
        <CanonicalDebateMessage
          key={record.message.id}
          record={record}
          bubbleWidth={chatLayout.bubbleWidth}
          judgeWidth={chatLayout.judgeWidth}
          pointQuestionsEnabled={canChallenge}
          selected={pointTarget?.message.id === record.message.id}
          onAskAbout={() => openPointQuestion(record)}
          onExplainTerm={(term) => selectExplanationTerm(record, term)}
        />
      ))}

      {drafts.map((draft) => (
        <DraftDebateMessage
          key={draft.messageId}
          draft={draft}
          frozen={pendingInterruption.current !== null}
          roundNumber={activeRoundNumber}
          bubbleWidth={chatLayout.bubbleWidth}
          judgeWidth={chatLayout.judgeWidth}
          onShowFull={() => {
            revealScheduler.current.showFull(draft.messageId);
            setRevealVersion((version) => version + 1);
          }}
        />
      ))}
      </View>

      {canChallenge ? (
        <View style={screenStyles.roundPauseCard}>
          <Text style={screenStyles.challengeEyebrow}>INTERIM JUDGE PAUSE</Text>
          <Text style={screenStyles.roundPauseText}>
            Ask about any completed point first. Explanations are educational and read-only; Round 2 starts only after a separate confirmation.
          </Text>
        </View>
      ) : null}

      {interruptionConfirmed ? (
        <InterruptionComposer
          value={interjection}
          onChange={(value) => {
            setInterjection(value);
            setInterjectionSaved(false);
            setInterruptionError("");
          }}
          onSave={() => void saveInterjection()}
          onExplainStoppedText={() => {
            if (interruptionPoint) openPointQuestion(interruptionPoint);
          }}
          onContinue={() => void continueInterruptedDebate()}
          onEnd={() => void endInterruptedDebate()}
          busy={interruptionBusy}
          saved={interjectionSaved}
          error={interruptionError || undefined}
          canExplainStoppedText={canExplainStoppedText}
          canContinue={interruptionJobSettled && savedInterjection !== null}
        />
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
    {pointTarget ? (
      <PointInquiryModal
        target={pointTarget}
        mode={pointDialogMode}
        selectedText={selectedText}
        question={question}
        selectedTextIsValid={selectedTextIsValid}
        canChallenge={canChallenge}
        canSubmitChallenge={canSubmitChallenge}
        canSubmitExplanation={canSubmitExplanation}
        challenging={challenging}
        explaining={explaining}
        explanationError={explanationError}
        explanationResult={explanationResult}
        onClose={closePointDialog}
        onSelectedTextChange={(value) => {
          invalidateExplanationRequest();
          setSelectedText(value);
          setExplanationResult(null);
          setExplanationError("");
          challengeKey.current = null;
        }}
        onQuestionChange={(value) => {
          invalidateExplanationRequest();
          setQuestion(value);
          setExplanationResult(null);
          setExplanationError("");
          challengeKey.current = null;
        }}
        onExplain={() => void submitExplanation()}
        onPrepareChallenge={prepareRoundTwoChallenge}
        onReturnToExplanation={returnToExplanation}
        onSubmitChallenge={() => void submitChallenge()}
      />
    ) : null}
    {hasNewMessages ? (
      <View
        accessibilityLiveRegion="polite"
        pointerEvents="box-none"
        style={screenStyles.newMessagesOverlay}
      >
        <FocusablePressable
          onPress={followLatestMessage}
          style={screenStyles.newMessagesButton}
          accessibilityLabel="Jump to new Debate messages"
          accessibilityRole="button"
        >
          <Text style={screenStyles.newMessagesText}>New messages ↓</Text>
        </FocusablePressable>
      </View>
    ) : null}
    </View>
  );
}

function PointInquiryModal({
  target,
  mode,
  selectedText,
  question,
  selectedTextIsValid,
  canChallenge,
  canSubmitExplanation,
  canSubmitChallenge,
  explaining,
  challenging,
  explanationResult,
  explanationError,
  onClose,
  onSelectedTextChange,
  onQuestionChange,
  onExplain,
  onPrepareChallenge,
  onReturnToExplanation,
  onSubmitChallenge,
}: {
  target: DebateMessageRecord;
  mode: PointInquiryMode;
  selectedText: string;
  question: string;
  selectedTextIsValid: boolean;
  canChallenge: boolean;
  canSubmitExplanation: boolean;
  canSubmitChallenge: boolean;
  explaining: boolean;
  challenging: boolean;
  explanationResult: ExplanationResult | null;
  explanationError: string;
  onClose: () => void;
  onSelectedTextChange: (value: string) => void;
  onQuestionChange: (value: string) => void;
  onExplain: () => void;
  onPrepareChallenge: () => void;
  onReturnToExplanation: () => void;
  onSubmitChallenge: () => void;
}) {
  const isChallengeConfirmation = mode === "challenge";
  const isInterruptedPrefix = !target.message.is_complete;
  const canDismiss = canDismissPointInquiry(challenging);
  const canPrepareChallenge = canPrepareRoundTwoChallenge({
    canChallenge,
    selectedTextIsValid,
    question,
    explaining,
  });
  return (
    <Modal
      animationType="fade"
      onRequestClose={() => {
        if (canDismiss) onClose();
      }}
      presentationStyle="overFullScreen"
      statusBarTranslucent
      transparent
      visible
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={screenStyles.modalRoot}
      >
        <TouchableWithoutFeedback
          accessible={false}
          disabled={!canDismiss}
          onPress={onClose}
        >
          <View style={screenStyles.modalBackdrop} />
        </TouchableWithoutFeedback>
        <View
          accessibilityLabel={isChallengeConfirmation
            ? "Confirm Round 2 challenge"
            : "Ask about this Debate point"}
          accessibilityViewIsModal
          style={screenStyles.modalCard}
        >
          <ScrollView
            contentContainerStyle={screenStyles.modalContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={screenStyles.rowBetween}>
              <Text
                style={[
                  screenStyles.modalEyebrow,
                  { color: isChallengeConfirmation ? colors.judge : colors.bull },
                ]}
              >
                {isChallengeConfirmation
                  ? "ROUND 2 · EXPLICIT CONFIRMATION"
                  : "EDUCATIONAL EXPLAINER · READ ONLY"}
              </Text>
              <FocusablePressable
                disabled={!canDismiss}
                onPress={onClose}
                style={[screenStyles.modalCloseButton, !canDismiss && screenStyles.disabledButton]}
                accessibilityRole="button"
                accessibilityLabel="Close this point dialog"
                accessibilityState={{ disabled: !canDismiss }}
              >
                <Text style={screenStyles.modalCloseText}>Close ×</Text>
              </FocusablePressable>
            </View>
            <Text style={screenStyles.modalTitle}>
              {isChallengeConfirmation
                ? "Start a second debate round?"
                : isInterruptedPrefix
                  ? "Ask about the stopped text"
                  : "Ask before you challenge"}
            </Text>
            <Text style={screenStyles.modalHelp}>
              {isChallengeConfirmation
                ? "This will commit your exact question and start Round 2. It is a Debate intervention, not an explanation."
                : isInterruptedPrefix
                  ? "Ask the Explainer about an exact passage in the frozen prefix. The response treats it as unfinished, has no unverified citations, and does not resume or change the Debate."
                  : "Ask the Explainer about this passage first. Its answer is educational, grounded in the completed message and linked evidence, and does not change the Debate."}
            </Text>

            <Text style={screenStyles.inputLabel}>
              EXACT PASSAGE · {rolePresentation(target.message.role).label}
            </Text>
            <TextInput
              value={selectedText}
              onChangeText={onSelectedTextChange}
              maxLength={500}
              multiline
              style={screenStyles.pointPassageInput}
              placeholder="Keep an exact passage from this message"
              placeholderTextColor={colors.muted}
              accessibilityLabel="Exact passage from the selected Debate message"
              accessibilityHint={isInterruptedPrefix
                ? "Edit this only to another exact passage from the same frozen prefix."
                : "Edit this only to another exact passage from the same completed message."}
            />
            {!selectedTextIsValid ? (
              <Text style={screenStyles.validationText}>
                Keep an exact passage that occurs in the selected message.
              </Text>
            ) : null}

            <Text style={screenStyles.inputLabel}>YOUR QUESTION</Text>
            <TextInput
              autoFocus
              value={question}
              onChangeText={onQuestionChange}
              maxLength={500}
              multiline
              style={screenStyles.textArea}
              placeholder={isChallengeConfirmation
                ? "What should both sides reconsider in Round 2?"
                : "What is unclear, or what would you like explained?"}
              placeholderTextColor={colors.muted}
              accessibilityLabel={isChallengeConfirmation
                ? "Question proposed for Round 2"
                : "Educational question about the selected point"}
            />

            {explanationError && !isChallengeConfirmation ? (
              <Text accessibilityLiveRegion="assertive" style={screenStyles.validationText}>
                {explanationError}
              </Text>
            ) : null}

            {isChallengeConfirmation ? (
              <>
                <FocusablePressable
                  disabled={!canSubmitChallenge}
                  style={[
                    screenStyles.challengeButton,
                    !canSubmitChallenge && screenStyles.disabledButton,
                  ]}
                  onPress={onSubmitChallenge}
                  accessibilityLabel="Confirm and start Round 2 with this challenge"
                  accessibilityRole="button"
                  accessibilityState={{ busy: challenging, disabled: !canSubmitChallenge }}
                >
                  {challenging ? <ActivityIndicator color={colors.background} size="small" /> : null}
                  <Text style={screenStyles.challengeButtonText}>
                    {challenging ? "Starting Round 2…" : "Start Round 2 with this challenge"}
                  </Text>
                </FocusablePressable>
                <FocusablePressable
                  disabled={challenging}
                  style={[screenStyles.modalSecondaryButton, challenging && screenStyles.disabledButton]}
                  onPress={onReturnToExplanation}
                  accessibilityLabel="Return to educational explanation"
                  accessibilityRole="button"
                  accessibilityState={{ disabled: challenging }}
                >
                  <Text style={screenStyles.modalSecondaryText}>← Back to explanation</Text>
                </FocusablePressable>
              </>
            ) : (
              <>
                <FocusablePressable
                  disabled={!canSubmitExplanation}
                  style={[
                    screenStyles.explanationButton,
                    !canSubmitExplanation && screenStyles.disabledButton,
                  ]}
                  onPress={onExplain}
                  accessibilityLabel="Ask the educational Explainer"
                  accessibilityRole="button"
                  accessibilityState={{ busy: explaining, disabled: !canSubmitExplanation }}
                >
                  {explaining ? <ActivityIndicator color={colors.background} size="small" /> : null}
                  <Text style={screenStyles.explanationButtonText}>
                    {explaining ? "Asking Explainer…" : "Ask Explainer"}
                  </Text>
                </FocusablePressable>
                {canChallenge ? (
                  <FocusablePressable
                    disabled={!canPrepareChallenge}
                    style={[
                      screenStyles.modalSecondaryButton,
                      !canPrepareChallenge && screenStyles.disabledButton,
                    ]}
                    onPress={onPrepareChallenge}
                    accessibilityLabel="Prepare this question as a Round 2 challenge"
                    accessibilityRole="button"
                    accessibilityState={{ disabled: !canPrepareChallenge }}
                  >
                    <Text style={screenStyles.modalSecondaryText}>Prepare a Round 2 challenge →</Text>
                  </FocusablePressable>
                ) : null}
              </>
            )}

            {explanationResult && !isChallengeConfirmation ? (
              <View accessibilityLiveRegion="polite" style={screenStyles.explanationResult}>
                <Text style={screenStyles.explanationResultTitle}>EXPLAINER ANSWER</Text>
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

            <FocusablePressable
              disabled={!canDismiss}
              style={[screenStyles.modalCancelButton, !canDismiss && screenStyles.disabledButton]}
              onPress={onClose}
              accessibilityLabel="Cancel and close this dialog"
              accessibilityRole="button"
              accessibilityState={{ disabled: !canDismiss }}
            >
              <Text style={screenStyles.modalCancelText}>Cancel</Text>
            </FocusablePressable>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
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
  explanationButton: { minHeight: 46, backgroundColor: colors.bull, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 12, marginTop: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  explanationButtonText: { color: colors.background, fontSize: 13, fontWeight: "900" },
  explanationResult: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 11, padding: 13, marginTop: 14 },
  explanationResultTitle: { color: colors.bull, fontSize: 11, fontWeight: "900", letterSpacing: 0.8 },
  explanationContent: { color: colors.text, fontSize: 13, lineHeight: 20, marginTop: 8 },
  explanationSafetyNote: { color: colors.warning, fontSize: 10, lineHeight: 16, marginTop: 10 },
  roundPauseCard: { backgroundColor: themeColors.surface.information, borderColor: colors.judge, borderWidth: 1, borderRadius: 14, padding: 13, marginTop: 8, marginBottom: 14 },
  challengeEyebrow: { color: colors.judge, fontSize: 10, fontWeight: "900", letterSpacing: 1.2 },
  roundPauseText: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 6 },
  inputLabel: { color: colors.muted, fontSize: 9, fontWeight: "900", letterSpacing: 1, marginTop: 7, marginBottom: 6 },
  textArea: { minHeight: 78, backgroundColor: colors.background, borderColor: colors.line, borderWidth: 1, borderRadius: 11, color: colors.text, padding: 12, fontSize: 13, lineHeight: 19, textAlignVertical: "top" },
  pointPassageInput: { maxHeight: 126, minHeight: 68, backgroundColor: colors.background, borderColor: colors.line, borderWidth: 1, borderRadius: 11, color: colors.text, padding: 12, fontSize: 12, lineHeight: 18, textAlignVertical: "top" },
  validationText: { color: colors.warning, fontSize: 10, marginTop: 5 },
  challengeButton: { minHeight: 46, backgroundColor: colors.cyan, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 12, marginTop: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  challengeButtonText: { color: colors.background, fontSize: 13, fontWeight: "900" },
  modalRoot: { alignItems: "center", flex: 1, justifyContent: "center", padding: 20 },
  modalBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(2, 8, 23, 0.78)" },
  modalCard: { backgroundColor: colors.elevated, borderColor: colors.line, borderRadius: 20, borderWidth: 1, maxHeight: "88%", maxWidth: 620, overflow: "hidden", width: "100%" },
  modalContent: { padding: 18 },
  modalEyebrow: { flex: 1, fontSize: 10, fontWeight: "900", letterSpacing: 1.1 },
  modalCloseButton: { alignItems: "center", justifyContent: "center", minHeight: interaction.minTargetSize, minWidth: interaction.minTargetSize, paddingHorizontal: 4 },
  modalCloseText: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  modalTitle: { color: colors.text, fontSize: 21, fontWeight: "900", lineHeight: 27, marginTop: 8 },
  modalHelp: { color: colors.muted, fontSize: 12, lineHeight: 19, marginBottom: 9, marginTop: 7 },
  modalSecondaryButton: { alignItems: "center", borderColor: colors.cyan, borderRadius: 11, borderWidth: 1, justifyContent: "center", marginTop: 10, minHeight: interaction.minTargetSize, paddingHorizontal: 14, paddingVertical: 10 },
  modalSecondaryText: { color: colors.cyan, fontSize: 12, fontWeight: "900" },
  modalCancelButton: { alignItems: "center", justifyContent: "center", marginTop: 10, minHeight: interaction.minTargetSize, paddingHorizontal: 12 },
  modalCancelText: { color: colors.muted, fontSize: 12, fontWeight: "800" },
  cancelButton: { minHeight: 44, borderColor: colors.bear, borderWidth: 1, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 11, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 4 },
  cancelText: { color: colors.bear, fontSize: 13, fontWeight: "800" },
  disabledButton: { opacity: 0.42 },
  newMessagesOverlay: { position: "absolute", left: 0, right: 0, bottom: 92, alignItems: "center" },
  newMessagesButton: { minHeight: interaction.minTargetSize, justifyContent: "center", backgroundColor: themeColors.action.primary, borderColor: themeColors.border.inverse, borderWidth: 1, borderRadius: 22, paddingHorizontal: 18, elevation: 8, boxShadow: "0px 8px 20px rgba(0,0,0,0.32)" },
  newMessagesText: { color: themeColors.content.onSignal, fontSize: 12, fontWeight: "900" },
  disclaimer: { color: colors.muted, fontSize: 10, lineHeight: 16, marginTop: 18 },
});
