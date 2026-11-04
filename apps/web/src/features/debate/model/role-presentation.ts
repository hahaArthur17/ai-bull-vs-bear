import type { DebateMessage } from "@/lib/contracts/research";

export const rolePresentation = {
  bull: {
    label: "The bull case",
    caption: "What could go right",
    initials: "B+",
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  },
  bear: {
    label: "The bear case",
    caption: "What deserves caution",
    initials: "B−",
    className:
      "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200",
  },
  judge: {
    label: "The synthesis",
    caption: "Weighing both perspectives",
    initials: "J",
    className:
      "border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200",
  },
} satisfies Record<
  DebateMessage["role"],
  {
    label: string;
    caption: string;
    initials: string;
    className: string;
  }
>;

export function roundLabel(role: DebateMessage["role"], index: number) {
  return role === "judge" ? "Final synthesis" : `Round ${Math.floor(index / 2) + 1}`;
}

export function sourceUrl(value?: string) {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
