import { graphemeSegments } from "unicode-segmenter/grapheme";
import type { DebateDraft } from "./debateStream.ts";
import type { DebateMessageRecord } from "./types.ts";

export const REVEAL_CADENCE_MS = 90;
export const MAX_PENDING_REVEAL_UNITS = 480;

type RevealSource = {
  messageId: string;
  role: DebateDraft["role"];
  generationId: string;
  content: string;
  citations: DebateDraft["citations"];
  record: DebateMessageRecord | null;
};

type RevealItem = RevealSource & {
  units: string[];
  revealedUnits: number;
  forceVisible: boolean;
};

export type RevealDisplay = {
  canonicalMessages: DebateMessageRecord[];
  drafts: DebateDraft[];
  activeMessageId: string | null;
};

const CJK_CHARACTER = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\uff00-\uffef]/u;
const WORD_OR_MARK = /[\p{L}\p{N}\p{M}]/u;

function graphemes(value: string): string[] {
  return Array.from(graphemeSegments(value), ({ segment }) => segment);
}

/**
 * Groups Latin-script text into display words while emitting CJK one grapheme at
 * a time. An unfinished trailing word stays buffered until a later delta makes
 * its boundary clear (or the provider completes the message).
 */
export function revealUnits(content: string, complete: boolean): string[] {
  if (!content) return [];
  const characters = graphemes(content);
  const units: string[] = [];
  let word = "";
  const flushWord = () => {
    if (word) {
      units.push(word);
      word = "";
    }
  };

  // The last cluster can still receive a combining mark, surrogate, or ZWJ
  // continuation in the next network delta. A whitespace boundary is stable.
  if (!complete && characters.length && !/^\s+$/u.test(characters[characters.length - 1])) {
    characters.pop();
  }
  for (const character of characters) {
    if (CJK_CHARACTER.test(character)) {
      flushWord();
      units.push(character);
    } else if (WORD_OR_MARK.test(character)) {
      word += character;
    } else {
      flushWord();
      units.push(character);
    }
  }
  if (complete) flushWord();
  return units;
}

export class RevealScheduler {
  private readonly items = new Map<string, RevealItem>();
  private initialized = false;
  private frozenDisplay: RevealDisplay | null = null;

  /** Freeze the last rendered display, not the newest received provider text. */
  freeze(display: RevealDisplay): void {
    this.frozenDisplay = display;
  }

  releaseFreeze(): void {
    this.frozenDisplay = null;
  }


  sync(
    canonicalMessages: DebateMessageRecord[],
    drafts: Record<string, DebateDraft>,
    options: { immediate?: boolean } = {},
  ): void {
    if (this.frozenDisplay) return;
    const orderedCanonicalMessages = [...canonicalMessages].sort(
      (left, right) => left.message.sequence_number - right.message.sequence_number,
    );
    const canonicalIds = new Set(orderedCanonicalMessages.map((record) => record.message.id));
    const sources: RevealSource[] = [
      ...orderedCanonicalMessages.map((record) => ({
        messageId: record.message.id,
        role: record.message.role as DebateDraft["role"],
        generationId: record.message.generation_id,
        content: record.message.content,
        citations: record.citations,
        record,
      })),
      // A completion and its final delta can arrive in the same React update.
      // The durable record wins if both forms of one message are present.
      ...Object.values(drafts)
        .filter((draft) => !canonicalIds.has(draft.messageId))
        .map((draft) => ({ ...draft, record: null })),
    ];

    const settleNewCanonical = !this.initialized || options.immediate === true;
    const nextItems = new Map<string, RevealItem>();
    for (const source of sources) {
      const previous = this.items.get(source.messageId);
      const units = revealUnits(source.content, source.record !== null);
      const revealImmediately = options.immediate === true
        || (!previous && settleNewCanonical && source.record !== null);
      nextItems.set(source.messageId, {
        ...source,
        units,
        revealedUnits: revealImmediately
          ? units.length
          : Math.min(previous?.revealedUnits || 0, units.length),
        forceVisible: revealImmediately || previous?.forceVisible === true,
      });
    }
    this.items.clear();
    for (const [messageId, item] of nextItems) this.items.set(messageId, item);
    this.initialized = true;
  }

  advance(): boolean {
    if (this.frozenDisplay) return false;
    const item = this.firstUnsettled();
    if (!item) return false;
    const remaining = item.units.length - item.revealedUnits;
    if (remaining <= 0) return false;
    // Keep latency bounded if provider output arrives far faster than the
    // display cadence. This reveals an ordered prefix; it never discards text.
    const increment = remaining > MAX_PENDING_REVEAL_UNITS
      ? Math.min(12, Math.ceil(remaining / MAX_PENDING_REVEAL_UNITS))
      : 1;
    item.revealedUnits += increment;
    return true;
  }

  showFull(messageId: string): void {
    if (this.frozenDisplay) return;
    const item = this.items.get(messageId);
    if (item) {
      item.revealedUnits = item.units.length;
      item.forceVisible = true;
    }
  }

  settleAll(): void {
    if (this.frozenDisplay) return;
    for (const item of this.items.values()) {
      item.revealedUnits = item.units.length;
      item.forceVisible = true;
    }
  }

  display(): RevealDisplay {
    if (this.frozenDisplay) return this.frozenDisplay;
    const canonicalMessages: DebateMessageRecord[] = [];
    const drafts: DebateDraft[] = [];
    let activeMessageId: string | null = null;

    for (const item of this.items.values()) {
      if (activeMessageId !== null) break;
      const isDrained = item.forceVisible || item.revealedUnits >= item.units.length;
      const isCanonical = item.record !== null && isDrained;
      if (isCanonical) {
        canonicalMessages.push(item.record as DebateMessageRecord);
        continue;
      }
      if (activeMessageId !== null) continue;
      activeMessageId = item.messageId;
      drafts.push({
        messageId: item.messageId,
        generationId: item.generationId,
        role: item.role,
        content: item.forceVisible ? item.content : item.units.slice(0, item.revealedUnits).join(""),
        nextDeltaIndex: 0,
        citations: item.citations,
      });
    }
    return { canonicalMessages, drafts, activeMessageId };
  }

  private firstUnsettled(): RevealItem | null {
    for (const item of this.items.values()) {
      if (item.record === null || item.revealedUnits < item.units.length) return item;
    }
    return null;
  }
}
