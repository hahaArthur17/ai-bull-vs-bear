import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

test("legacy diagnostics label real provider usage without calling it demo usage", () => {
  const source = readFileSync(join(process.cwd(), "src/screens/LegacyDebateScreen.tsx"), "utf8");

  assert.match(source, /Token usage: \{analysis\.token_usage\.total_tokens\} total/);
  assert.match(source, /prompt \{analysis\.token_usage\.prompt_tokens\}/);
  assert.match(source, /completion \{analysis\.token_usage\.completion_tokens\}/);
  assert.doesNotMatch(source, /demo tokens/);
});
