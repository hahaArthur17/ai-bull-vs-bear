import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import { api } from "../api";
import type { InterruptionComposerBusy } from "../components/debate/InterruptionComposer";
import {
  createCanonicalDebateSnapshot,
  type DebateStreamClient,
  type DebateStreamSnapshot,
} from "../debateStream";
import { defaultPointPassage, exactExplanationTerm } from "../explanationView";
import {
  activeInterruptionDraft,
  canStopBeforeOutput,
  canStopVisibleDraft,
  findInterjection,
  findInterruptedMessage,
  interruptionIdempotencyKey,
  isInterruptionJobPending,
  shouldReconnectAfterInterruptionEnd,
  shouldStopBeforeOutput,
} from "../interruptionState";
import { canCancelDebate, visibleDebateDrafts } from "../liveDebateView";
import {
  confirmPendingInterruption,
  createPendingInterruption,
  loadPendingInterruption,
  pendingInterruptionIsObsolete,
  pendingInterruptionWasSaved,
  savePendingInterruption,
  type PendingInterruption,
} from "../pendingInterruption";
import type { DebateSessionDetail } from "../types";
import type { useDebateReveal } from "./useDebateReveal";

const interruptionsEnabled = process.env.EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED === "true";

type InterruptionOptions = {
  accountId: string;
  sessionId: string;
  initialDetail: DebateSessionDetail;
  snapshot: DebateStreamSnapshot;
  currentSessionId: RefObject<string>;
  streamClient: RefObject<DebateStreamClient | null>;
  recoveryReady: boolean;
  setRecoveryReady: Dispatch<SetStateAction<boolean>>;
  setSnapshot: Dispatch<SetStateAction<DebateStreamSnapshot>>;
  setStreamEpoch: Dispatch<SetStateAction<number>>;
  setActionError: Dispatch<SetStateAction<string>>;
  reveal: ReturnType<typeof useDebateReveal>;
};

/** Compose recovery, Stop and viewpoint mutations without mixing their lifecycles. */
export function useDebateInterruption(options: InterruptionOptions) {
  const state = useInterruptionState(options);
  usePendingStopRecovery(options, state.pendingInterruption);
  useInterruptionSettlement(options);
  const stop = useStopDebate(options, state.pendingInterruption);
  const actions = useInterjectionActions(options, state);
  return { ...state, ...stop, ...actions };
}

function useInterruptionState({ snapshot, sessionId, recoveryReady }: InterruptionOptions) {
  const [interjection, setInterjection] = useState("");
  const [interjectionSaved, setInterjectionSaved] = useState(false);
  const [interruptionBusy, setInterruptionBusy] = useState<InterruptionComposerBusy>(null);
  const [interruptionError, setInterruptionError] = useState("");
  const pendingInterruption = useRef<PendingInterruption | null>(null);
  const interruptionHydration = useRef<string | null>(null);
  const interruptionPoint = findInterruptedMessage(snapshot.canonicalMessages);
  const savedInterjection = interruptionPoint
    ? findInterjection(
        snapshot.canonicalMessages,
        interruptionPoint.message.id,
        snapshot.activeGenerationId || "",
      )
    : null;
  const interruptionConfirmed =
    interruptionsEnabled &&
    recoveryReady &&
    pendingInterruption.current === null &&
    snapshot.sessionStatus === "interrupted_awaiting_user" &&
    snapshot.activeGenerationId !== null &&
    interruptionPoint !== null;
  const interruptionJobSettled = !isInterruptionJobPending(snapshot.jobStatus);
  const canExplainStoppedText =
    interruptionPoint !== null &&
    exactExplanationTerm(
      interruptionPoint,
      defaultPointPassage(interruptionPoint.message.content),
    ) !== null;
  useEffect(() => {
    setInterjection("");
    setInterjectionSaved(false);
    setInterruptionBusy(null);
    setInterruptionError("");
    pendingInterruption.current = null;
    interruptionHydration.current = null;
  }, [sessionId]);

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

  return {
    pendingInterruption,
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
    setInterruptionBusy,
  };
}

type InterruptionState = ReturnType<typeof useInterruptionState>;

function usePendingStopRecovery(
  {
    accountId,
    sessionId,
    initialDetail,
    setRecoveryReady,
    setActionError,
    reveal,
  }: InterruptionOptions,
  pendingInterruption: RefObject<PendingInterruption | null>,
) {
  const { revealScheduler } = reveal;
  useEffect(() => {
    if (!interruptionsEnabled) return;
    let active = true;
    setRecoveryReady(false);
    void loadPendingInterruption(AsyncStorage, accountId, sessionId)
      .then(async (pending) => {
        if (!active) return;
        if (pending) {
          if (
            pendingInterruptionWasSaved(initialDetail, pending) ||
            pendingInterruptionIsObsolete(initialDetail, pending)
          ) {
            await confirmPendingInterruption(
              AsyncStorage,
              accountId,
              sessionId,
              pending.idempotencyKey,
            );
            if (!active) return;
          } else {
            pendingInterruption.current = pending;
            const visibleIds = new Set(pending.precedingMessageIds);
            revealScheduler.current.freeze({
              canonicalMessages: initialDetail.messages.filter((record) =>
                visibleIds.has(record.message.id),
              ),
              drafts: [
                {
                  messageId: pending.messageId,
                  generationId: pending.generationId,
                  role: pending.role,
                  content: pending.visiblePrefix,
                  citations: [],
                  nextDeltaIndex: 0,
                },
              ],
              activeMessageId: pending.messageId,
            });
            setActionError("A previous Stop is not confirmed. Text stays frozen; retry Stop here.");
          }
        }
        setRecoveryReady(true);
      })
      .catch(() => {
        if (active)
          setActionError(
            "Could not check the saved Stop request. Reopen this Debate to retry safely.",
          );
      });
    return () => {
      active = false;
    };
  }, [accountId, sessionId]);
}

function useInterruptionSettlement({
  snapshot,
  sessionId,
  recoveryReady,
  setSnapshot,
}: InterruptionOptions) {
  useEffect(() => {
    if (
      !interruptionsEnabled ||
      !recoveryReady ||
      snapshot.sessionStatus !== "interrupted_awaiting_user" ||
      !isInterruptionJobPending(snapshot.jobStatus)
    )
      return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const schedule = (delay: number) => {
      timer = setTimeout(() => {
        void poll();
      }, delay);
    };
    const poll = async () => {
      try {
        const detail = await api.getDebate(sessionId);
        if (!active) return;
        setSnapshot((current) => {
          // A GET started before Save or Continue must not roll the newer
          // canonical transcript back after that mutation succeeds.
          if (
            current.sessionStatus !== "interrupted_awaiting_user" ||
            !isInterruptionJobPending(current.jobStatus) ||
            current.activeGenerationId !== detail.session.active_generation_id ||
            detail.messages.length < current.canonicalMessages.length
          )
            return current;
          return createCanonicalDebateSnapshot(detail, current.lastSequence, current.status);
        });
        const serverJobPending =
          detail.session.status === "interrupted_awaiting_user" &&
          (detail.job?.status === "queued" || detail.job?.status === "running");
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
  }, [
    recoveryReady,
    sessionId,
    snapshot.canonicalMessages.length,
    snapshot.jobStatus,
    snapshot.sessionStatus,
  ]);
}

function useStopDebate(
  {
    snapshot,
    accountId,
    sessionId,
    currentSessionId,
    streamClient,
    setSnapshot,
    setStreamEpoch,
    setActionError,
    reveal,
  }: InterruptionOptions,
  pendingInterruption: RefObject<PendingInterruption | null>,
) {
  const { revealScheduler, revealDisplay, setRevealVersion } = reveal;
  const [cancelling, setCancelling] = useState(false);
  const drafts = visibleDebateDrafts(revealDisplay.drafts);
  const canCancel =
    (interruptionsEnabled
      ? Boolean(
          pendingInterruption.current ||
          canStopVisibleDraft(snapshot, drafts[0]) ||
          canStopBeforeOutput(snapshot),
        )
      : canCancelDebate(snapshot)) && !cancelling;
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
        const generationId =
          pending?.generationId || providerDraft?.generationId || snapshot.activeGenerationId;
        const draftRole = providerDraft?.role || visible?.role;
        const target =
          pending ||
          createPendingInterruption({
            accountId,
            sessionId,
            generationId,
            // The before-output endpoint creates its stable empty anchor with
            // the generation ID. A visible draft already has a message ID.
            messageId: beforeOutput ? generationId : providerDraft!.messageId,
            visiblePrefix: beforeOutput ? "" : visible?.content || "",
            role:
              draftRole === "bull" || draftRole === "bear" || draftRole === "judge"
                ? draftRole
                : "system",
            precedingMessageIds: revealDisplay.canonicalMessages.map((record) => record.message.id),
          });
        pendingInterruption.current = target;
        setRevealVersion((version) => version + 1);
        await savePendingInterruption(AsyncStorage, target);
        if (currentSessionId.current !== sessionId) return;
        detail = beforeOutput
          ? await api.interruptBeforeOutputDebate(sessionId, target.generationId)
          : await api.interruptDebate(sessionId, {
              generationId: target.generationId,
              messageId: target.messageId,
              content: target.visiblePrefix,
            });
        if (currentSessionId.current !== sessionId) return;
        if (!pendingInterruptionWasSaved(detail, target)) {
          throw new Error("Stop was not confirmed. Text remains frozen; retry Stop here.");
        }
        if (
          !(await confirmPendingInterruption(
            AsyncStorage,
            accountId,
            sessionId,
            target.idempotencyKey,
          ))
        )
          return;
        if (currentSessionId.current !== sessionId) return;
        pendingInterruption.current = null;
        revealScheduler.current.releaseFreeze();
        revealScheduler.current.sync(detail.messages, {}, { immediate: true });
      } else {
        detail = await api.cancelDebate(sessionId, snapshot.activeGenerationId);
      }
      if (currentSessionId.current !== sessionId) return;
      setSnapshot((current) =>
        createCanonicalDebateSnapshot(detail, current.lastSequence, current.status),
      );
    } catch (error) {
      if (currentSessionId.current !== sessionId) return;
      const pending = pendingInterruption.current;
      if (interruptionsEnabled && pending) {
        try {
          const latest = await api.getDebate(sessionId);
          if (currentSessionId.current !== sessionId) return;
          const saved = pendingInterruptionWasSaved(latest, pending);
          if (saved || pendingInterruptionIsObsolete(latest, pending)) {
            if (
              !(await confirmPendingInterruption(
                AsyncStorage,
                accountId,
                sessionId,
                pending.idempotencyKey,
              ))
            )
              return;
            if (currentSessionId.current !== sessionId) return;
            pendingInterruption.current = null;
            revealScheduler.current.releaseFreeze();
            revealScheduler.current.sync(latest.messages, {}, { immediate: true });
            setSnapshot((current) =>
              createCanonicalDebateSnapshot(latest, current.lastSequence, current.status),
            );
            if (!saved) setStreamEpoch((current) => current + 1);
            setActionError(
              saved
                ? ""
                : "That turn finished before Stop here could take effect. You can try again on the next live turn.",
            );
            return;
          }
        } catch {
          // Preserve the saved prefix until the server can confirm its state.
        }
      }
      setActionError(
        interruptionsEnabled
          ? "Stop was not confirmed. Text remains frozen; retry Stop here."
          : error instanceof Error
            ? error.message
            : "Could not cancel this Debate.",
      );
    } finally {
      if (currentSessionId.current === sessionId) setCancelling(false);
    }
  };

  useEffect(() => {
    setCancelling(false);
  }, [sessionId]);
  return { cancelling, canCancel, cancelDebate };
}

function useInterjectionActions(
  {
    snapshot,
    sessionId,
    currentSessionId,
    streamClient,
    setSnapshot,
    setStreamEpoch,
  }: InterruptionOptions,
  {
    interruptionConfirmed,
    interruptionPoint,
    interjection,
    interruptionJobSettled,
    savedInterjection,
    interruptionBusy,
    setInterruptionBusy,
    setInterruptionError,
    setInterjection,
    setInterjectionSaved,
  }: InterruptionState,
) {
  const interjectionKey = useRef<{ identity: string; key: string } | null>(null);
  const continuationKey = useRef<{ identity: string; key: string } | null>(null);
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
      interjectionKey.current = {
        identity,
        key: interruptionIdempotencyKey("interject", identity),
      };
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
      if (currentSessionId.current !== sessionId) return;
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
      if (currentSessionId.current !== sessionId) return;
      setInterjectionSaved(false);
      setInterruptionError(
        error instanceof Error ? error.message : "Could not save your viewpoint.",
      );
    } finally {
      if (currentSessionId.current === sessionId) setInterruptionBusy(null);
    }
  };

  const continueInterruptedDebate = async () => {
    if (
      !interruptionConfirmed ||
      !interruptionPoint ||
      !savedInterjection ||
      !interruptionJobSettled ||
      interruptionBusy !== null
    )
      return;
    const waitingGenerationId = snapshot.activeGenerationId;
    if (!waitingGenerationId) return;
    // Continue job identifiers are scoped to the waiting generation. A later
    // stop at the same frozen point needs a fresh job key while retries for
    // this request keep the same key.
    const identity = `${waitingGenerationId}:${interruptionPoint.message.generation_id}:${savedInterjection.message.id}`;
    if (continuationKey.current?.identity !== identity) {
      continuationKey.current = {
        identity,
        key: interruptionIdempotencyKey("continue", identity),
      };
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
      if (currentSessionId.current !== sessionId) return;
      setSnapshot(createCanonicalDebateSnapshot(detail));
      setStreamEpoch((current) => current + 1);
    } catch (error) {
      if (currentSessionId.current !== sessionId) return;
      setInterruptionError(
        error instanceof Error ? error.message : "Could not continue the Debate.",
      );
    } finally {
      if (currentSessionId.current === sessionId) setInterruptionBusy(null);
    }
  };

  const endInterruptedDebate = async () => {
    if (!interruptionConfirmed || !interruptionPoint || interruptionBusy !== null) return;
    setInterruptionBusy("end");
    setInterruptionError("");
    try {
      const detail = await api.endInterruptedDebate(sessionId, interruptionPoint.message.id);
      if (currentSessionId.current !== sessionId) return;
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
      if (currentSessionId.current !== sessionId) return;
      setInterruptionError(error instanceof Error ? error.message : "Could not end the Debate.");
    } finally {
      if (currentSessionId.current === sessionId) setInterruptionBusy(null);
    }
  };

  useEffect(() => {
    interjectionKey.current = null;
    continuationKey.current = null;
  }, [sessionId]);
  return { saveInterjection, continueInterruptedDebate, endInterruptedDebate };
}
