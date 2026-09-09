import type {
  DebateEvent,
  DebateMessage,
  DebateMessageEvidence,
  DebateMessagePresentation,
  DebateMessageRecord,
  DebateSessionDetail,
  DebateSessionStatus,
} from "./types";

export type DebateDraft = {
  messageId: string;
  generationId: string;
  role: "bull" | "bear" | "judge" | "explainer";
  content: string;
  nextDeltaIndex: number;
  citations: DebateMessageEvidence[];
};

export type DebateStreamStatus =
  | "idle"
  | "connecting"
  | "live"
  | "reconnecting"
  | "closed"
  | "failed";

export type DebateJobViewStatus =
  | "none"
  | "queued"
  | "running"
  | "retry_scheduled"
  | "stage_completed"
  | "failed"
  | "cancelled";

export type DebateStreamSnapshot = {
  status: DebateStreamStatus;
  sessionStatus: DebateSessionStatus | null;
  canonicalMessages: DebateMessageRecord[];
  drafts: Record<string, DebateDraft>;
  lastSequence: number;
  activeGenerationId: string | null;
  jobId: string | null;
  jobStatus: DebateJobViewStatus;
  jobAttemptCount: number;
  retryDelaySeconds: number | null;
  safeError: string | null;
};

type SseFrame = { id: string | null; event: string; data: string };

type StreamOptions = {
  url: string;
  accessToken: string | null;
  afterSequence: number;
  signal: AbortSignal;
  onEvent: (event: DebateEvent) => void;
};

export interface DebateEventTransport {
  open(options: StreamOptions): Promise<void>;
}

export class DebateCursorExpiredError extends Error {
  readonly latestSequence: number | null;

  constructor(latestSequence: number | null) {
    super("Debate event cursor expired");
    this.latestSequence = latestSequence;
  }
}

class DebateProtocolGapError extends Error {
  readonly observedSequence: number;

  constructor(observedSequence: number) {
    super("Debate event sequence or delta gap detected");
    this.observedSequence = observedSequence;
  }
}

export class SseFrameParser {
  private buffer = "";

  push(fragment: string): SseFrame[] {
    this.buffer = (this.buffer + fragment).replace(/\r\n/g, "\n");
    const frames: SseFrame[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const frame = this.parseBlock(block);
      if (frame) frames.push(frame);
      boundary = this.buffer.indexOf("\n\n");
    }
    return frames;
  }

  private parseBlock(block: string): SseFrame | null {
    let id: string | null = null;
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const separator = line.indexOf(":");
      const field = separator >= 0 ? line.slice(0, separator) : line;
      const rawValue = separator >= 0 ? line.slice(separator + 1) : "";
      const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
      if (field === "id") id = value;
      if (field === "event") event = value;
      if (field === "data") data.push(value);
    }
    return data.length ? { id, event, data: data.join("\n") } : null;
  }
}

function isDebateEvent(value: unknown): value is DebateEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Partial<DebateEvent>;
  return event.version === 1
    && typeof event.event_id === "string"
    && typeof event.session_id === "string"
    && Number.isInteger(event.sequence)
    && typeof event.type === "string"
    && !!event.payload
    && typeof event.payload === "object";
}

function parseLatestSequence(xhr: XMLHttpRequest): number | null {
  const header = xhr.getResponseHeader("X-Debate-Latest-Sequence");
  if (header === null || !header.trim()) return null;
  const value = Number(header);
  return Number.isInteger(value) && value >= 0 ? value : null;
}

export class XhrDebateEventTransport implements DebateEventTransport {
  open(options: StreamOptions): Promise<void> {
    return new Promise((resolve, reject) => {
      if (typeof XMLHttpRequest === "undefined") {
        reject(new Error("Streaming transport is unavailable on this runtime"));
        return;
      }
      const parser = new SseFrameParser();
      const xhr = new XMLHttpRequest();
      let consumedCharacters = 0;
      let settled = false;

      const cleanup = () => options.signal.removeEventListener("abort", abort);
      const finish = (error?: Error) => {
        if (settled) return;
        settled = true;
        cleanup();
        if (error) reject(error);
        else resolve();
      };
      const abort = () => {
        xhr.abort();
        finish();
      };
      const consume = () => {
        const next = xhr.responseText.slice(consumedCharacters);
        consumedCharacters = xhr.responseText.length;
        try {
          for (const frame of parser.push(next)) {
            const payload: unknown = JSON.parse(frame.data);
            if (!isDebateEvent(payload) || payload.type !== frame.event) {
              throw new Error("Invalid Debate event envelope");
            }
            options.onEvent(payload);
          }
        } catch (error) {
          xhr.abort();
          finish(error instanceof Error ? error : new Error("Invalid Debate event"));
        }
      };

      const separator = options.url.includes("?") ? "&" : "?";
      xhr.open(
        "GET",
        `${options.url}${separator}after_sequence=${options.afterSequence}`,
        true,
      );
      xhr.setRequestHeader("Accept", "text/event-stream");
      if (options.accessToken) {
        xhr.setRequestHeader("Authorization", `Bearer ${options.accessToken}`);
      }
      xhr.onprogress = consume;
      xhr.onerror = () => finish(new Error("Debate event connection failed"));
      xhr.onload = () => {
        if (xhr.status === 409) {
          finish(new DebateCursorExpiredError(parseLatestSequence(xhr)));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          finish(new Error(`Debate event connection failed (${xhr.status})`));
          return;
        }
        consume();
        finish();
      };
      options.signal.addEventListener("abort", abort, { once: true });
      if (options.signal.aborted) abort();
      else xhr.send();
    });
  }
}

const TERMINAL_EVENT_TYPES = new Set<DebateEvent["type"]>([
  "session.awaiting_user",
  "session.interrupted_awaiting_user",
  "session.completed",
  "session.cancelled",
  "session.failed",
]);

const TERMINAL_SESSION_STATUSES = new Set<DebateSessionDetail["session"]["status"]>([
  "awaiting_user",
  "interrupted_awaiting_user",
  "completed",
  "cancelled",
  "failed",
]);

const SESSION_STATUSES = new Set<DebateSessionStatus>([
  "created",
  "queued_round_1",
  "running_round_1",
  "awaiting_user",
  "interrupted_awaiting_user",
  "queued_round_2",
  "running_round_2",
  "completed",
  "cancel_requested",
  "cancelled",
  "failed",
]);

function canonicalJobStatus(detail: DebateSessionDetail): DebateJobViewStatus {
  if (detail.job?.status === "completed") return "stage_completed";
  if (detail.job) return detail.job.status;
  if (detail.session.status === "failed") return "failed";
  if (detail.session.status === "cancelled") return "cancelled";
  if (
    detail.session.status === "completed"
    || detail.session.status === "awaiting_user"
  ) return "stage_completed";
  if (detail.session.status.startsWith("queued_")) return "queued";
  if (detail.session.status.startsWith("running_")) return "running";
  return "none";
}

function stringPayload(event: DebateEvent, key: string): string | null {
  const value = event.payload[key];
  return typeof value === "string" ? value : null;
}

function numberPayload(event: DebateEvent, key: string): number | null {
  const value = event.payload[key];
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

function sessionStatusPayload(event: DebateEvent): DebateSessionStatus | null {
  const status = stringPayload(event, "status");
  return status && SESSION_STATUSES.has(status as DebateSessionStatus)
    ? status as DebateSessionStatus
    : null;
}

function isDebateMessage(value: unknown): value is DebateMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<DebateMessage>;
  return typeof message.id === "string"
    && typeof message.generation_id === "string"
    && Number.isInteger(message.sequence_number)
    && typeof message.content === "string"
    && message.is_complete === true;
}

function isFreshness(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const freshness = value as Record<string, unknown>;
  return (freshness.status === "current" || freshness.status === "stale" || freshness.status === "unknown")
    && (freshness.age_days === undefined || freshness.age_days === null || Number.isInteger(freshness.age_days))
    && (freshness.max_age_days === undefined || freshness.max_age_days === null || Number.isInteger(freshness.max_age_days))
    && (freshness.evaluated_at === undefined || freshness.evaluated_at === null || typeof freshness.evaluated_at === "string");
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isDebateMessagePresentation(value: unknown): value is DebateMessagePresentation {
  if (!value || typeof value !== "object") return false;
  const presentation = value as Record<string, unknown>;
  if (
    typeof presentation.argument !== "string"
    || !isNullableString(presentation.interpretation)
    || !isNullableString(presentation.uncertainty)
    || !Array.isArray(presentation.facts_used)
  ) return false;
  return presentation.facts_used.every((fact) => {
    if (!fact || typeof fact !== "object") return false;
    const evidence = fact as Record<string, unknown>;
    return typeof evidence.evidence_id === "string"
      && (evidence.evidence_type === "news" || evidence.evidence_type === "filing" || evidence.evidence_type === "technical" || evidence.evidence_type === null)
      && isNullableString(evidence.title)
      && isNullableString(evidence.fact)
      && isNullableString(evidence.source)
      && isNullableString(evidence.date)
      && isFreshness(evidence.freshness)
      && isNullableString(evidence.support_span)
      && isNullableString(evidence.source_destination)
      && Array.isArray(evidence.missing_metadata)
      && evidence.missing_metadata.every((item) => (
        item === "evidence_type"
        || item === "title"
        || item === "fact"
        || item === "source"
        || item === "date"
        || item === "support_span"
        || item === "source_destination"
      ));
  });
}

function presentationPayload(event: DebateEvent): DebateMessagePresentation | null {
  const value = event.payload.presentation;
  if (value === undefined || value === null) return null;
  if (!isDebateMessagePresentation(value)) throw new DebateProtocolGapError(event.sequence);
  return value;
}

function orderedMessages(records: DebateMessageRecord[]): DebateMessageRecord[] {
  return [...records].sort(
    (left, right) => left.message.sequence_number - right.message.sequence_number,
  );
}

function upsertMessage(
  records: DebateMessageRecord[],
  record: DebateMessageRecord,
): DebateMessageRecord[] {
  return orderedMessages([
    ...records.filter((item) => item.message.id !== record.message.id),
    record,
  ]);
}

type Reduction = {
  snapshot: DebateStreamSnapshot;
  terminal: boolean;
};

export function reduceDebateEvent(
  current: DebateStreamSnapshot,
  event: DebateEvent,
): Reduction {
  if (event.type === "heartbeat") return { snapshot: current, terminal: false };
  if (event.sequence <= current.lastSequence) return { snapshot: current, terminal: false };
  if (current.lastSequence > 0 && event.sequence !== current.lastSequence + 1) {
    throw new DebateProtocolGapError(event.sequence);
  }

  const generationId = stringPayload(event, "generation_id");
  let activeGenerationId = current.activeGenerationId;
  let drafts = { ...current.drafts };
  let canonicalMessages = current.canonicalMessages;
  let sessionStatus = sessionStatusPayload(event) || current.sessionStatus;
  let jobId = current.jobId;
  let jobStatus = current.jobStatus;
  let jobAttemptCount = current.jobAttemptCount;
  let retryDelaySeconds = current.retryDelaySeconds;
  if ((event.type === "session.created" || event.type === "job.queued") && generationId) {
    activeGenerationId = generationId;
    drafts = {};
  }
  if (
    (event.type === "session.cancel_requested" || event.type === "session.cancelled"
      || event.type === "session.interrupted_awaiting_user")
    && generationId
  ) {
    activeGenerationId = generationId;
    drafts = {};
  }
  const isLateGeneration = generationId !== null
    && activeGenerationId !== null
    && generationId !== activeGenerationId;
  if (isLateGeneration) {
    return {
      snapshot: { ...current, lastSequence: event.sequence },
      terminal: false,
    };
  }

  if (event.type.startsWith("job.")) {
    jobId = stringPayload(event, "job_id") || jobId;
  }
  if (event.type === "job.queued") {
    jobStatus = "queued";
    jobAttemptCount = 0;
    retryDelaySeconds = null;
  }
  if (event.type === "job.started") {
    jobStatus = "running";
    jobAttemptCount = numberPayload(event, "attempt_count") || jobAttemptCount;
    retryDelaySeconds = null;
  }
  if (event.type === "job.retry_scheduled") {
    jobStatus = "retry_scheduled";
    jobAttemptCount = numberPayload(event, "attempt_count") || jobAttemptCount;
    retryDelaySeconds = numberPayload(event, "retry_delay_seconds");
  }
  if (event.type === "job.failed" || event.type === "session.failed") {
    jobStatus = "failed";
    jobAttemptCount = numberPayload(event, "attempt_count") || jobAttemptCount;
    retryDelaySeconds = null;
  }
  if (event.type === "session.interrupted_awaiting_user") {
    jobStatus = "cancelled";
    sessionStatus = "interrupted_awaiting_user";
    retryDelaySeconds = null;
  }
  if (event.type === "session.cancelled") {
    jobStatus = "cancelled";
    sessionStatus = "cancelled";
    retryDelaySeconds = null;
  }
  if (event.type === "session.awaiting_user" || event.type === "session.completed") {
    jobStatus = "stage_completed";
    sessionStatus = event.type === "session.awaiting_user" ? "awaiting_user" : "completed";
    retryDelaySeconds = null;
  }

  if (
    event.type === "turn.started"
    || event.type === "judge.started"
    || event.type === "explanation.started"
  ) {
    const messageId = stringPayload(event, "message_id");
    const role = event.type === "judge.started"
      ? "judge"
      : event.type === "explanation.started"
        ? "explainer"
        : event.payload.role;
    if (
      !messageId
      || !generationId
      || (role !== "bull" && role !== "bear" && role !== "judge" && role !== "explainer")
    ) {
      throw new DebateProtocolGapError(event.sequence);
    }
    drafts[messageId] = {
      messageId,
      generationId,
      role,
      content: "",
      nextDeltaIndex: 1,
      citations: [],
    };
  }

  if (
    event.type === "turn.delta"
    || event.type === "judge.delta"
    || event.type === "explanation.delta"
  ) {
    const messageId = stringPayload(event, "message_id");
    const delta = stringPayload(event, "delta");
    const deltaIndex = numberPayload(event, "delta_index");
    const draft = messageId ? drafts[messageId] : null;
    if (!draft || delta === null || deltaIndex !== draft.nextDeltaIndex) {
      throw new DebateProtocolGapError(event.sequence);
    }
    drafts[messageId as string] = {
      ...draft,
      content: draft.content + delta,
      nextDeltaIndex: draft.nextDeltaIndex + 1,
    };
  }

  if (event.type === "turn.citation") {
    const messageId = stringPayload(event, "message_id");
    const evidenceId = stringPayload(event, "evidence_id");
    const citationOrder = numberPayload(event, "citation_order");
    const supportSpan = event.payload.support_span;
    const draft = messageId ? drafts[messageId] : null;
    if (
      !draft
      || !messageId
      || !evidenceId
      || citationOrder === null
      || (supportSpan !== undefined && supportSpan !== null && typeof supportSpan !== "string")
    ) {
      throw new DebateProtocolGapError(event.sequence);
    }
    drafts[messageId] = {
      ...draft,
      citations: [
        ...draft.citations.filter((citation) => citation.evidence_id !== evidenceId),
        {
          message_id: messageId,
          evidence_id: evidenceId,
          citation_order: citationOrder,
          support_span: typeof supportSpan === "string" ? supportSpan : null,
          metadata: {},
        },
      ].sort((left, right) => left.citation_order - right.citation_order),
    };
  }

  if (
    event.type === "turn.completed"
    || event.type === "judge.completed"
    || event.type === "explanation.completed"
  ) {
    const message = event.payload.message;
    if (!isDebateMessage(message)) throw new DebateProtocolGapError(event.sequence);
    const draft = drafts[message.id];
    if (
      message.generation_id !== (generationId || activeGenerationId)
      // The current deterministic Judge sends judge.started followed directly
      // by judge.completed. A future streaming Judge supplies ordered deltas,
      // which retain the stricter exact-content check used for Turn streams.
      || (draft && draft.content !== message.content
        && !(event.type === "judge.completed" && draft.nextDeltaIndex === 1 && draft.content === ""))
    ) {
      throw new DebateProtocolGapError(event.sequence);
    }
    const citations = draft?.citations || (current.canonicalMessages.find(
      (record) => record.message.id === message.id,
    )?.citations || []);
    const existing = current.canonicalMessages.find(
      (record) => record.message.id === message.id,
    );
    canonicalMessages = upsertMessage(canonicalMessages, {
      message,
      citations,
      // A presentation is server-authored. Older retained events omit it, so
      // retain any detail payload already loaded instead of inferring facts on
      // the client.
      presentation: presentationPayload(event) ?? existing?.presentation ?? null,
    });
    delete drafts[message.id];
  }

  const terminal = TERMINAL_EVENT_TYPES.has(event.type);
  if (terminal) drafts = {};
  return {
    snapshot: {
      ...current,
      status: terminal ? "closed" : "live",
      sessionStatus,
      canonicalMessages,
      drafts,
      lastSequence: event.sequence,
      activeGenerationId,
      jobId,
      jobStatus,
      jobAttemptCount,
      retryDelaySeconds,
      safeError: event.type === "session.failed"
        ? stringPayload(event, "safe_error_code") || "Debate generation failed"
        : current.safeError,
    },
    terminal,
  };
}

type DebateStreamClientOptions = {
  eventUrl: string;
  getAccessToken: () => Promise<string | null>;
  loadCanonical: () => Promise<DebateSessionDetail>;
  onSnapshot: (snapshot: DebateStreamSnapshot) => void;
  transport?: DebateEventTransport;
  maxReconnectAttempts?: number;
};

export class DebateStreamClient {
  private readonly options: DebateStreamClientOptions;
  private readonly transport: DebateEventTransport;
  private readonly maxReconnectAttempts: number;
  private controller: AbortController | null = null;
  private stopped = true;
  private snapshot: DebateStreamSnapshot = {
    status: "idle",
    sessionStatus: null,
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: null,
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };

  constructor(options: DebateStreamClientOptions) {
    this.options = options;
    this.transport = options.transport || new XhrDebateEventTransport();
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 4;
  }

  async start(): Promise<void> {
    this.stop();
    this.stopped = false;
    this.controller = new AbortController();
    await this.reloadCanonical(0, "connecting");
    if (this.stopped || this.isCanonicalTerminal()) return;

    let attempts = 0;
    while (!this.stopped && attempts <= this.maxReconnectAttempts) {
      let terminalEvent = false;
      try {
        const accessToken = await this.options.getAccessToken();
        await this.transport.open({
          url: this.options.eventUrl,
          accessToken,
          afterSequence: this.snapshot.lastSequence,
          signal: this.controller.signal,
          onEvent: (event) => {
            const reduced = reduceDebateEvent(this.snapshot, event);
            this.snapshot = reduced.snapshot;
            terminalEvent = terminalEvent || reduced.terminal;
            this.emit();
          },
        });
        if (this.stopped || terminalEvent) return;
        attempts += 1;
      } catch (error) {
        if (this.stopped) return;
        if (error instanceof DebateCursorExpiredError) {
          if (error.latestSequence === null) throw error;
          await this.reloadCanonical(error.latestSequence, "reconnecting");
          if (this.isCanonicalTerminal()) return;
          attempts = 0;
          continue;
        }
        if (error instanceof DebateProtocolGapError) {
          await this.reloadCanonical(error.observedSequence, "reconnecting");
          if (this.isCanonicalTerminal()) return;
          attempts = 0;
          continue;
        }
        attempts += 1;
      }
      if (!this.stopped && attempts <= this.maxReconnectAttempts) {
        this.snapshot = { ...this.snapshot, status: "reconnecting" };
        this.emit();
        await new Promise((resolve) => setTimeout(resolve, Math.min(250 * 2 ** attempts, 2000)));
      }
    }
    if (!this.stopped) {
      this.snapshot = {
        ...this.snapshot,
        status: "failed",
        drafts: {},
        safeError: "The live Debate connection could not be restored.",
      };
      this.emit();
    }
  }

  stop(): void {
    this.stopped = true;
    this.controller?.abort();
    this.controller = null;
  }

  private async reloadCanonical(
    lastSequence: number,
    status: DebateStreamStatus,
  ): Promise<void> {
    const detail = await this.options.loadCanonical();
    this.snapshot = createCanonicalDebateSnapshot(detail, lastSequence, status);
    this.emit();
  }

  private isCanonicalTerminal(): boolean {
    return this.snapshot.status === "closed";
  }

  private emit(): void {
    this.options.onSnapshot(this.snapshot);
  }
}

export function createCanonicalDebateSnapshot(
  detail: DebateSessionDetail,
  lastSequence = 0,
  status: DebateStreamStatus = "connecting",
): DebateStreamSnapshot {
  return {
    status: TERMINAL_SESSION_STATUSES.has(detail.session.status) ? "closed" : status,
    sessionStatus: detail.session.status,
    canonicalMessages: orderedMessages(detail.messages),
    drafts: {},
    lastSequence,
    activeGenerationId: detail.session.active_generation_id,
    jobId: detail.job?.id || null,
    jobStatus: canonicalJobStatus(detail),
    jobAttemptCount: detail.job?.attempt_count || 0,
    retryDelaySeconds: null,
    safeError: detail.session.safe_error_code || null,
  };
}
