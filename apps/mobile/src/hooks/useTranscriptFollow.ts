import { useEffect, useRef, useState, type RefObject } from "react";
import { ScrollView, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import { shouldAnimateTranscriptScroll, shouldAutoFollowTranscript } from "../debateChatView";
import type { DebateStreamSnapshot } from "../debateStream";

/** Follow output only while the reader stays near the transcript's end. */
export function useTranscriptFollow(
  snapshot: DebateStreamSnapshot,
  sessionId: string,
  reduceMotionEnabled: RefObject<boolean | null>,
) {
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const scrollRef = useRef<ScrollView | null>(null);
  const scrollFrame = useRef<number | null>(null);
  const followsTranscript = useRef(true);
  useEffect(() => {
    if (snapshot.lastSequence === 0) return;
    if (!followsTranscript.current) {
      setHasNewMessages(true);
      return;
    }
    scheduleTranscriptFollow(true);
  }, [snapshot.canonicalMessages.length, snapshot.lastSequence]);

  useEffect(
    () => () => {
      if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
    },
    [],
  );

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

  useEffect(() => {
    followsTranscript.current = true;
    setHasNewMessages(false);
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
    }
  }, [sessionId]);
  return {
    scrollRef,
    followsTranscript,
    hasNewMessages,
    updateTranscriptFollow,
    followLatestMessage,
    scheduleTranscriptFollow,
  };
}
