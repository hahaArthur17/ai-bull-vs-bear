import { z } from "zod";

const modeSchema = z.enum(["demo", "api"]);
const feedbackModeSchema = z.enum(["demo", "api", "disabled"]);

export function parseConfig(env: Record<string, string | boolean | undefined>) {
  const demoBuild = env.MODE === "demo" || env.MODE === "test";
  const dataMode = modeSchema.parse(env.VITE_DATA_MODE ?? (demoBuild ? "demo" : undefined));
  const feedbackMode = feedbackModeSchema.parse(
    env.VITE_FEEDBACK_MODE ?? (demoBuild ? "demo" : undefined),
  );
  const apiBaseUrl = String(env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
  const feedbackApiBaseUrl = String(env.VITE_FEEDBACK_API_BASE_URL ?? "").replace(/\/$/, "");
  if (dataMode === "api") validateReceiver(apiBaseUrl, "Research");
  if (feedbackMode === "api") validateReceiver(feedbackApiBaseUrl, "Feedback");
  return { dataMode, apiBaseUrl, feedbackMode, feedbackApiBaseUrl };
}

function validateReceiver(value: string, feature: string) {
  const url = z.url().safeParse(value);
  if (!url.success) throw new Error(`${feature} API needs an explicit receiver URL.`);
  const parsed = new URL(value);
  if (
    parsed.protocol !== "https:" &&
    !(parsed.protocol === "http:" && ["localhost", "127.0.0.1"].includes(parsed.hostname))
  ) {
    throw new Error(`${feature} API must use HTTPS, or localhost for development.`);
  }
}

export const config = parseConfig(import.meta.env);
export default config;
