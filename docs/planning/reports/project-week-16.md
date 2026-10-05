# Project Week 16 — V2 Live Interruption and Research UI Handoff

Date: 2026-10-05

Status: Local fixes committed; target-device and release acceptance remain open.

## Completed work

- `12b20c5` isolates client workspace state across account changes and
  simplifies Watchlist and Stock Detail copy/layout without removing data
  warnings or accessibility labels.
- `0c9fdb2` fixes live-stream finalization and source-claim handling, keeps
  blocking repository reads off the SSE/Worker event loop, and reduces saved
  Debate message/citation reads to a bounded owner-checked query.
- `fac5d59` hardens Stop confirmation, stale SSE rejection, persisted pending
  recovery, and ambiguous Round 2 Challenge submission.
- `358c365` excludes local presentation submissions from Git.

## Verification and live state

The last recorded code pass completed 542 backend tests, 122 mobile tests,
TypeScript checking, and `git diff --check`. The authenticated AAPL Session
`2b6831a2-2f33-5629-bdcc-a403c9ec9c2b` used real model calls and reached
the Final Judge after Stop → Explanation → interjection → Continue in each
round. History reopened 17 canonical records, including two incomplete
prefixes. The provider ledger reported 50,380 Debate tokens plus one
unknown-usage attempt; Explanation usage was not measured. The earlier failed
Session remains a safe-failure record. The completed Session's first Bull
message predates the new source-quote guard, so it cannot serve as a wholly
post-guard source audit.

## Decisions and remaining work

Saved messages are not rewritten retroactively. Earlier Groq v1 content is
labelled in the client, while new output receives conservative source checks.
Model-linked citations still require a human to inspect the actual excerpt
for consequential claims. Account state is reset on identity change, while
server authorization/RLS remains the canonical security boundary.

1. Review the full Stock Detail and Watchlist layouts and switch two accounts
   on the target simulator/device, including delayed requests.
2. Measure cold and warm saved-Debate reopen after the read reduction; add V2
   in-app provider/usage diagnostics with unknown usage represented honestly.
3. Run a fresh budgeted post-guard source audit and test Stop/recovery under
   background/foreground and weak-network conditions before device acceptance.

Material incident details and their verification limits are in
[`issue-log.md`](../issue-log.md). Current instructions are in
[`v2-beta-resume-checklist.md`](../v2-beta-resume-checklist.md).
