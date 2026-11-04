import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { AccessibilityInfo, AppState } from "react-native";
import type { DebateStreamSnapshot } from "../debateStream";
import { REVEAL_CADENCE_MS, RevealScheduler } from "../revealScheduler";

/** Keep display timing separate from received and durably completed provider text. */
export function useDebateReveal(
  snapshot: DebateStreamSnapshot,
  recoveryReady: boolean,
  setStreamEpoch: Dispatch<SetStateAction<number>>,
) {
  const [, setRevealVersion] = useState(0);
  const reduceMotionEnabled = useRef<boolean | null>(null);
  const screenReaderEnabled = useRef<boolean | null>(null);
  const appIsActive = useRef(AppState.currentState === "active");
  const revealScheduler = useRef(new RevealScheduler());

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
      subscription?.remove();
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
    const subscription = AccessibilityInfo.addEventListener(
      "screenReaderChanged",
      applyScreenReader,
    );
    void AccessibilityInfo.isScreenReaderEnabled()
      .then(applyScreenReader)
      .catch(() => {
        // The visible scheduler remains usable when this native preference is unavailable.
      });
    return () => {
      mounted = false;
      subscription?.remove();
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
    return () => subscription?.remove();
  }, [setStreamEpoch]);

  useEffect(() => {
    if (!recoveryReady) return;
    revealScheduler.current.sync(snapshot.canonicalMessages, snapshot.drafts, {
      immediate:
        reduceMotionEnabled.current === true ||
        screenReaderEnabled.current === true ||
        !appIsActive.current ||
        snapshot.status === "reconnecting" ||
        snapshot.sessionStatus === "completed",
    });
    setRevealVersion((version) => version + 1);
  }, [snapshot, recoveryReady]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (
        reduceMotionEnabled.current === true ||
        screenReaderEnabled.current === true ||
        !appIsActive.current
      )
        return;
      if (revealScheduler.current.advance()) setRevealVersion((version) => version + 1);
    }, REVEAL_CADENCE_MS);
    return () => clearInterval(timer);
  }, []);

  const revealDisplay = recoveryReady
    ? revealScheduler.current.display()
    : { canonicalMessages: [], drafts: [], activeMessageId: null };
  return {
    revealScheduler,
    revealDisplay,
    setRevealVersion,
    reduceMotionEnabled,
  };
}
