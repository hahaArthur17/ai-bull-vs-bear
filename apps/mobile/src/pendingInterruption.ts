export const PENDING_INTERRUPTION_STORAGE_VERSION = 1;
export const MAX_PENDING_INTERRUPTION_PREFIX_LENGTH = 6_000;

const STORAGE_KEY_PREFIX = "ai-bull-vs-bear:pending-interruptions";
const MAX_IDENTIFIER_LENGTH = 256;
const MAX_PRECEDING_MESSAGE_IDS = 100;

export type PendingInterruptionStorage = {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
};

export type PendingInterruptionInput = {
  accountId: string;
  sessionId: string;
  generationId: string;
  messageId: string;
  visiblePrefix: string;
  role: PendingInterruptionRole;
  precedingMessageIds: string[];
};

export type PendingInterruptionRole = "bull" | "bear" | "judge" | "system";

export type PendingInterruption = PendingInterruptionInput & {
  idempotencyKey: string;
};

type StoredPendingInterruptions = {
  version: typeof PENDING_INTERRUPTION_STORAGE_VERSION;
  entries: Record<string, PendingInterruption>;
};

function storageKey(accountId: string): string {
  return `${STORAGE_KEY_PREFIX}:v${PENDING_INTERRUPTION_STORAGE_VERSION}:${encodeURIComponent(accountId)}`;
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= MAX_IDENTIFIER_LENGTH;
}

function isRole(value: unknown): value is PendingInterruptionRole {
  return value === "bull" || value === "bear" || value === "judge" || value === "system";
}

function isPrecedingMessageIds(value: unknown): value is string[] {
  return Array.isArray(value)
    && value.length <= MAX_PRECEDING_MESSAGE_IDS
    && value.every(isIdentifier);
}

function isPendingInterruption(
  value: unknown,
  accountId?: string,
  allowLegacyDisplay = false,
): value is PendingInterruption {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return isIdentifier(candidate.accountId)
    && (accountId === undefined || candidate.accountId === accountId)
    && isIdentifier(candidate.sessionId)
    && isIdentifier(candidate.generationId)
    && isIdentifier(candidate.messageId)
    && isIdentifier(candidate.idempotencyKey)
    && typeof candidate.visiblePrefix === "string"
    && Array.from(candidate.visiblePrefix).length <= MAX_PENDING_INTERRUPTION_PREFIX_LENGTH
    && ((isRole(candidate.role) && isPrecedingMessageIds(candidate.precedingMessageIds))
      || (allowLegacyDisplay && candidate.role === undefined && candidate.precedingMessageIds === undefined));
}

function isStoredPendingInterruptions(value: unknown, accountId: string): value is StoredPendingInterruptions {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  if (candidate.version !== PENDING_INTERRUPTION_STORAGE_VERSION
    || !candidate.entries || typeof candidate.entries !== "object"
    || Array.isArray(candidate.entries)) return false;
  return Object.entries(candidate.entries).every(([sessionId, entry]) =>
    sessionId.length > 0 && isPendingInterruption(entry, accountId, true) && entry.sessionId === sessionId,
  );
}

function copyEntries(entries: Record<string, PendingInterruption>): Record<string, PendingInterruption> {
  const copied = Object.create(null) as Record<string, PendingInterruption>;
  for (const [sessionId, entry] of Object.entries(entries)) {
    copied[sessionId] = {
      ...entry,
      role: isRole(entry.role) ? entry.role : "system",
      precedingMessageIds: isPrecedingMessageIds(entry.precedingMessageIds)
        ? [...entry.precedingMessageIds]
        : [],
    };
  }
  return copied;
}

function stableHash(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36);
}

export function createPendingInterruption(input: PendingInterruptionInput): PendingInterruption {
  if (!isPendingInterruption({ ...input, idempotencyKey: "pending" })) {
    throw new Error("Pending interruption must contain bounded account, session, generation, message, and visible prefix values.");
  }
  const identity = [
    PENDING_INTERRUPTION_STORAGE_VERSION,
    input.accountId,
    input.sessionId,
    input.generationId,
    input.messageId,
    input.visiblePrefix,
  ].join("\u0000");
  return {
    ...input,
    idempotencyKey: `interrupt_${stableHash(identity)}`,
  };
}

async function readEntries(
  storage: PendingInterruptionStorage,
  accountId: string,
): Promise<StoredPendingInterruptions> {
  const key = storageKey(accountId);
  const raw = await storage.getItem(key);
  if (raw === null) {
    return { version: PENDING_INTERRUPTION_STORAGE_VERSION, entries: Object.create(null) };
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isStoredPendingInterruptions(parsed, accountId)) {
      return { ...parsed, entries: copyEntries(parsed.entries) };
    }
  } catch {
    // Treat corrupt JSON as unrecoverable rather than retrying another account's request.
  }
  await storage.removeItem(key);
  return { version: PENDING_INTERRUPTION_STORAGE_VERSION, entries: Object.create(null) };
}

export async function savePendingInterruption(
  storage: PendingInterruptionStorage,
  pending: PendingInterruption,
): Promise<void> {
  if (!isPendingInterruption(pending)) {
    throw new Error("Cannot save an invalid pending interruption.");
  }
  const stored = await readEntries(storage, pending.accountId);
  stored.entries[pending.sessionId] = pending;
  await storage.setItem(storageKey(pending.accountId), JSON.stringify(stored));
}

export async function loadPendingInterruption(
  storage: PendingInterruptionStorage,
  accountId: string,
  sessionId: string,
): Promise<PendingInterruption | null> {
  if (!isIdentifier(accountId) || !isIdentifier(sessionId)) return null;
  const stored = await readEntries(storage, accountId);
  return stored.entries[sessionId] || null;
}

export async function confirmPendingInterruption(
  storage: PendingInterruptionStorage,
  accountId: string,
  sessionId: string,
  expectedIdempotencyKey: string,
): Promise<boolean> {
  if (!isIdentifier(accountId) || !isIdentifier(sessionId) || !isIdentifier(expectedIdempotencyKey)) return false;
  const stored = await readEntries(storage, accountId);
  const pending = stored.entries[sessionId];
  if (!pending || pending.idempotencyKey !== expectedIdempotencyKey) return false;
  delete stored.entries[sessionId];
  const key = storageKey(accountId);
  if (Object.keys(stored.entries).length === 0) {
    await storage.removeItem(key);
    return true;
  }
  await storage.setItem(key, JSON.stringify(stored));
  return true;
}

export async function clearPendingInterruptionsForAccount(
  storage: PendingInterruptionStorage,
  accountId: string,
): Promise<void> {
  if (!isIdentifier(accountId)) return;
  await storage.removeItem(storageKey(accountId));
}
