import { describe, expect, it } from "vitest";
import { parseConfig } from "./env";

describe("independent research and feedback modes", () => {
  it("allows demo research with an explicit real feedback receiver", () => {
    expect(
      parseConfig({
        MODE: "demo",
        VITE_FEEDBACK_MODE: "api",
        VITE_FEEDBACK_API_BASE_URL: "https://feedback.example.com/",
      }),
    ).toMatchObject({
      dataMode: "demo",
      feedbackMode: "api",
      feedbackApiBaseUrl: "https://feedback.example.com",
    });
  });
  it("does not quietly fall back from invalid or missing real configuration", () => {
    expect(() => parseConfig({ MODE: "production" })).toThrow();
    expect(() => parseConfig({ MODE: "demo", VITE_FEEDBACK_MODE: "api" })).toThrow(/receiver/);
    expect(() =>
      parseConfig({
        MODE: "demo",
        VITE_FEEDBACK_MODE: "api",
        VITE_FEEDBACK_API_BASE_URL: "http://unknown.example.com",
      }),
    ).toThrow(/HTTPS/);
  });
});
