import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

test("legacy diagnostics label real provider usage without calling it demo usage", () => {
  // JSX formatters may insert explicit spaces or wrap expressions; the labels
  // must still identify real token counts without depending on source layout.
  const source = readFileSync(join(process.cwd(), "src/screens/LegacyDebateScreen.tsx"), "utf8")
    .replace(/\{\s*["'] ["']\s*\}/g, " ")
    .replace(/\s+/g, " ");

  assert.match(source, /Token usage: \{analysis\.token_usage\.total_tokens\} total/);
  assert.match(source, /prompt \{analysis\.token_usage\.prompt_tokens\}/);
  assert.match(source, /completion \{analysis\.token_usage\.completion_tokens\}/);
  assert.doesNotMatch(source, /demo tokens/);
});
