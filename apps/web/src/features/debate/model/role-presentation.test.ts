import { describe, expect, it } from "vitest";
import { roundLabel, sourceUrl } from "./role-presentation";

describe("debate presentation boundaries", () => {
  it("labels paired perspectives and keeps the judge separate", () => {
    expect(roundLabel("bull", 0)).toBe("Round 1");
    expect(roundLabel("bear", 1)).toBe("Round 1");
    expect(roundLabel("bull", 2)).toBe("Round 2");
    expect(roundLabel("judge", 4)).toBe("Final synthesis");
  });

  it("only offers navigable web evidence sources", () => {
    expect(sourceUrl("https://example.com/report")).toBe("https://example.com/report");
    expect(sourceUrl("javascript:alert(1)")).toBeUndefined();
    expect(sourceUrl("data:text/html,test")).toBeUndefined();
    expect(sourceUrl("not a URL")).toBeUndefined();
  });
});
