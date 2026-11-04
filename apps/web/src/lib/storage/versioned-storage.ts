import type { z } from "zod";

const prefix = "counterpoint.demo.v1.";
const memory = new Map<string, string>();
type DemoStorageKey = "watchlist" | "history";

function readRaw(key: string): string | null {
  if (memory.has(key)) return memory.get(key) ?? null;
  try {
    return window.localStorage.getItem(prefix + key) ?? memory.get(key) ?? null;
  } catch {
    return memory.get(key) ?? null;
  }
}

export function readDemoValue<T>(key: DemoStorageKey, schema: z.ZodType<T>, fallback: T): T {
  try {
    const raw = readRaw(key);
    if (!raw) return structuredClone(fallback);
    const envelope: unknown = JSON.parse(raw);
    if (!envelope || typeof envelope !== "object") return structuredClone(fallback);
    const { version, data } = envelope as { version?: unknown; data?: unknown };
    const parsed = schema.safeParse(data);
    return version === 1 && parsed.success ? parsed.data : structuredClone(fallback);
  } catch {
    return structuredClone(fallback);
  }
}

export function writeDemoValue<T>(key: DemoStorageKey, data: T): void {
  const raw = JSON.stringify({ version: 1, data });
  memory.set(key, raw);
  try {
    window.localStorage.setItem(prefix + key, raw);
  } catch {
    // In private or restricted browsers, the current demo remains usable in memory.
  }
}

export function clearDemoStorage(): void {
  for (const key of ["watchlist", "history"]) {
    memory.delete(key);
    try {
      window.localStorage.removeItem(prefix + key);
    } catch {
      // There is no persistent state to clear when browser storage is blocked.
    }
  }
}
