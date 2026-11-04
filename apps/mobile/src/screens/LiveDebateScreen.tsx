import React, { useEffect, useRef, useState } from "react";
import { ScrollView, Text, useWindowDimensions, View } from "react-native";
import {
  DebateStatusPanel,
  DebateStopControl,
  shortId,
} from "../components/debate/DebateStatusPanel";
import { PointInquiryModal } from "../components/debate/PointInquiryModal";
import { screenStyles } from "../components/debate/debateStyles";
import { useDebateInterruption } from "../hooks/useDebateInterruption";
import { useDebateReveal } from "../hooks/useDebateReveal";
import { usePointInquiry } from "../hooks/usePointInquiry";
import { useTranscriptFollow } from "../hooks/useTranscriptFollow";

import { createDebateStreamClient } from "../api";
import { FocusablePressable } from "../components/common";
import { InterruptionComposer } from "../components/debate/InterruptionComposer";
import { CanonicalDebateMessage, DraftDebateMessage } from "../components/debate/LiveDebateMessage";
import { debateActionStatus } from "../debateActionState";
import { debatePhaseBadge, getDebateChatLayout } from "../debateChatView";
import type { DebateStreamClient, DebateStreamSnapshot } from "../debateStream";
import { createCanonicalDebateSnapshot } from "../debateStream";
import { hasEarlierUnverifiedGroqMessages } from "../legacyGrounding";
import { canChallengeDebate, visibleDebateDrafts } from "../liveDebateView";
import { RevealScheduler } from "../revealScheduler";
import type { DebateSessionDetail } from "../types";

type LiveDebateScreenProps = {
  accountId: string;
  ticker: string;
  initialDetail: DebateSessionDetail;
  onBack: () => void;
};

const interruptionsEnabled = process.env.EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED === "true";
const LIVE_CONNECTION_ERROR =
  "Live updates could not start. Canonical completed messages remain safe.";

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
  const streamClient = useRef<DebateStreamClient | null>(null);
  const { width: viewportWidth } = useWindowDimensions();
  const chatLayout = getDebateChatLayout(viewportWidth);
  const sessionId = initialDetail.session.id;
  const currentSessionId = useRef(sessionId);
  currentSessionId.current = sessionId;

  useEffect(() => {
    currentSessionId.current = sessionId;
    return () => {
      currentSessionId.current = "";
    };
  }, [sessionId]);

  const reveal = useDebateReveal(snapshot, recoveryReady, setStreamEpoch);
  const { revealScheduler, revealDisplay, setRevealVersion, reduceMotionEnabled } = reveal;

  const {
    pendingInterruption,
    cancelling,
    canCancel,
    cancelDebate,
    interruptionConfirmed,
    interruptionPoint,
    interjection,
    interjectionSaved,
    interruptionBusy,
    interruptionError,
    interruptionJobSettled,
    canExplainStoppedText,
    savedInterjection,
    setInterjection,
    setInterjectionSaved,
    setInterruptionError,
    saveInterjection,
    continueInterruptedDebate,
    endInterruptedDebate,
  } = useDebateInterruption({
    accountId,
    sessionId,
    initialDetail,
    snapshot,
    currentSessionId,
    streamClient,
    recoveryReady,
    setRecoveryReady,
    setSnapshot,
    setStreamEpoch,
    setActionError,
    reveal,
  });
  const {
    scrollRef,
    followsTranscript,
    hasNewMessages,
    updateTranscriptFollow,
    followLatestMessage,
    scheduleTranscriptFollow,
  } = useTranscriptFollow(snapshot, sessionId, reduceMotionEnabled);

  useEffect(() => {
    setSnapshot(createCanonicalDebateSnapshot(initialDetail));
    setConnectionError("");
    setActionError("");
    revealScheduler.current = new RevealScheduler();
  }, [sessionId]);

  useEffect(() => {
    if (!recoveryReady || pendingInterruption.current) return;
    let mounted = true;
    const client = createDebateStreamClient(sessionId, (next) => {
      if (!mounted) return;
      setSnapshot(next);
      if (next.status === "failed") setConnectionError(LIVE_CONNECTION_ERROR);
      else if (next.status === "live" || next.status === "closed") setConnectionError("");
    });
    streamClient.current = client;
    setConnectionError("");
    void client.start().catch(() => {
      if (mounted) {
        setConnectionError(LIVE_CONNECTION_ERROR);
      }
    });
    return () => {
      mounted = false;
      client.stop();
      if (streamClient.current === client) streamClient.current = null;
    };
  }, [sessionId, streamEpoch, recoveryReady]);

  const showEarlierSourceWarning = hasEarlierUnverifiedGroqMessages(snapshot.canonicalMessages);
  const allDrafts = revealDisplay.drafts;
  const drafts = visibleDebateDrafts(allDrafts);
  const awaitingFirstSafeText = allDrafts.length > 0 && drafts.length === 0;
  const activeRoundNumber =
    snapshot.sessionStatus === "queued_round_2" ||
    snapshot.sessionStatus === "running_round_2" ||
    snapshot.canonicalMessages.some(({ message }) => message.round_number === 2)
      ? 2
      : 1;
  const canChallenge = !pendingInterruption.current && canChallengeDebate(snapshot);
  const {
    pointTarget,
    pointDialogMode,
    selectedText,
    question,
    selectedTextIsValid,
    canSubmitChallenge,
    canSubmitExplanation,
    challenging,
    explaining,
    explanationResult,
    explanationError,
    openPointQuestion,
    selectExplanationTerm,
    closePointDialog,
    prepareRoundTwoChallenge,
    returnToExplanation,
    submitChallenge,
    submitExplanation,
    invalidateExplanationRequest,
    setSelectedText,
    setQuestion,
    setExplanationResult,
    setExplanationError,
    challengeKey,
  } = usePointInquiry({
    sessionId,
    canChallenge,
    currentSessionId,
    setSnapshot,
    setStreamEpoch,
    setActionError,
  });
  const activeAction = debateActionStatus({
    cancelling,
    challenging,
    explaining,
  });

  const statusPanel = <DebateStatusPanel snapshot={snapshot} />;
  const cancelControl = (
    <DebateStopControl canCancel={canCancel} cancelling={cancelling} onStop={cancelDebate} />
  );

  return (
    <View style={screenStyles.screen}>
      <ScrollView
        ref={scrollRef}
        style={screenStyles.scroll}
        contentContainerStyle={[screenStyles.page, { paddingHorizontal: chatLayout.pagePadding }]}
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
              Session {shortId(sessionId)} ·{" "}
              {initialDetail.execution_mode === "queued" ? "DURABLE QUEUE" : "SYNC PREVIEW"}
            </Text>
          </View>
          <View style={screenStyles.liveBadge}>
            <View style={screenStyles.liveDot} />
            <Text style={screenStyles.liveText}>
              {debatePhaseBadge(snapshot.sessionStatus, snapshot.status)}
            </Text>
          </View>
        </View>

        <View
          style={[
            screenStyles.workspace,
            chatLayout.showStatusRail && screenStyles.workspaceDesktop,
          ]}
        >
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

            {showEarlierSourceWarning ? (
              <View style={screenStyles.warningCard}>
                <Text style={screenStyles.warningText}>
                  Earlier AI messages predate source-quote checks. Citations link excerpts, but do
                  not verify every claim.
                </Text>
              </View>
            ) : null}

            {revealDisplay.canonicalMessages.length === 0 && drafts.length === 0 ? (
              <View style={screenStyles.emptyCard}>
                <Text style={screenStyles.emptyTitle}>
                  {awaitingFirstSafeText
                    ? "The agent is preparing a safe first response"
                    : "The transcript is intentionally empty"}
                </Text>
                <Text style={screenStyles.emptyText}>
                  {awaitingFirstSafeText
                    ? "Nothing is shown as a chat message until the first safe text is available."
                    : "Queue admission returned before generation. Messages will appear here only after a Worker starts; partial output stays visually distinct from durable output."}
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
                  Ask about any completed point first. Explanations are educational and read-only;
                  Round 2 starts only after a separate confirmation.
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
                <Text style={screenStyles.railNote}>
                  Connection controls remain available in the transcript.
                </Text>
              ) : null}
              {cancelControl}
            </View>
          ) : null}
        </View>

        <Text style={screenStyles.disclaimer}>
          Educational analysis. Citations link excerpts; they do not verify every claim. No trading
          instructions.
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
          actionError={actionError}
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
