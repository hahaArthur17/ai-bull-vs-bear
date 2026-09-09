import { layout } from "./theme/tokens.ts";
import type { DebateMessage, DebateSessionStatus } from "./types.ts";

export type DebateChatLayout = {
  bubbleWidth: "92%" | "84%" | "72%" | "68%";
  judgeWidth: "96%" | "88%" | "78%" | "74%";
  pagePadding: 14 | 18 | 24 | 28;
  showStatusRail: boolean;
};

export type DebateMessagePlacement = {
  alignment: "left" | "right" | "center";
  kind: "bull" | "bear" | "user" | "judge" | "system";
  label: string;
};

export function getDebateChatLayout(viewportWidth: number): DebateChatLayout {
  if (viewportWidth >= layout.breakpoints.desktop) {
    return {
      bubbleWidth: "68%",
      judgeWidth: "74%",
      pagePadding: 28,
      showStatusRail: true,
    };
  }
  if (viewportWidth >= layout.breakpoints.tablet) {
    return {
      bubbleWidth: "72%",
      judgeWidth: "78%",
      pagePadding: 24,
      showStatusRail: false,
    };
  }
  if (viewportWidth >= layout.breakpoints.phone) {
    return {
      bubbleWidth: "84%",
      judgeWidth: "88%",
      pagePadding: 18,
      showStatusRail: false,
    };
  }
  return {
    bubbleWidth: "92%",
    judgeWidth: "96%",
    pagePadding: 14,
    showStatusRail: false,
  };
}

export function getDebateMessagePlacement(
  role: DebateMessage["role"],
  roundNumber: number,
): DebateMessagePlacement {
  if (role === "bull") return { alignment: "left", kind: "bull", label: "Bull agent" };
  if (role === "bear") return { alignment: "right", kind: "bear", label: "Bear agent" };
  if (role === "user") return { alignment: "center", kind: "user", label: "Your challenge" };
  if (role === "judge") {
    return {
      alignment: "center",
      kind: "judge",
      label: roundNumber === 2 ? "Final neutral Judge" : "Interim neutral Judge",
    };
  }
  return {
    alignment: "center",
    kind: "system",
    label: role === "explainer" ? "Explainer" : "System",
  };
}

export function shouldAutoFollowTranscript(
  contentHeight: number,
  viewportHeight: number,
  offsetY: number,
  threshold = 96,
): boolean {
  if (contentHeight <= viewportHeight) return true;
  return contentHeight - viewportHeight - offsetY <= threshold;
}

export function shouldAnimateTranscriptScroll(
  reduceMotionEnabled: boolean | null,
): boolean {
  return reduceMotionEnabled === false;
}

export function debatePhaseBadge(
  sessionStatus: DebateSessionStatus | null,
  connectionStatus: string,
): string {
  if (sessionStatus === "interrupted_awaiting_user") return "STOPPED HERE";
  if (sessionStatus === "awaiting_user") return "ROUND 1 PAUSED";
  if (sessionStatus === "completed") return "FINAL";
  if (sessionStatus === "cancelled") return "CANCELLED";
  if (sessionStatus === "failed") return "FAILED";
  if (sessionStatus === "queued_round_1") return "ROUND 1 QUEUED";
  if (sessionStatus === "running_round_1") return "ROUND 1 LIVE";
  if (sessionStatus === "queued_round_2") return "ROUND 2 QUEUED";
  if (sessionStatus === "running_round_2") return "ROUND 2 LIVE";
  return connectionStatus.toUpperCase();
}
