# Project Issue Log

This is the append-only record of material project issues. It preserves the
facts needed for status reports and for a future maintainer to resume an
investigation without relying on chat context.

## How to record an issue

Add a dated entry whenever an incident, data-integrity defect, deployment
failure, access-control problem, or external-provider limitation materially
affects the project. Record:

- the user-visible symptom and affected scope;
- verified evidence and the current confidence in the diagnosis;
- mitigation, verification, and the commit or configuration change involved;
- the remaining follow-up and its owner.

Do not include API keys, tokens, passwords, service-role credentials, or other
secrets. Link to an existing weekly report for broader context rather than
duplicating implementation detail.

---

## 2026-10-17 — Dependency audit changed and Node 20 CI became stale

**Status:** CI runtime corrected; dependency remediation remains open.
Related historical record: 2026-09-12 SDK54 npm audit findings below.

**Symptom and evidence**

A clean locked install audited 709 packages and reported 37 findings (9
moderate, 27 high, 1 critical), superseding the old 18/zero-critical count.
`npm ls shell-quote --all` traced the critical npm finding to
`react-native@0.81.5 → react-devtools-core@6.1.5 → shell-quote@1.10.0`.
The [upstream advisory](https://github.com/advisories/GHSA-pqg4-j6r4-53mv)
identifies 1.11.0 as patched. No exploit was reproduced in this pass.
Separately, locked Supabase packages declare Node >=22, while CI still
selected Node 20 and the mobile tests use native TypeScript execution.

**Mitigation and verification**

Documentation now records the dated audit rather than claiming zero critical
findings or assuming an SDK jump is the only fix. CI selects Node 24, matching
the locally verified runtime. A stale local types directory caused the first
typecheck failure; `npm ci` restored it without manifest/lockfile edits.
542 backend tests, 122 mobile tests, typecheck, Expo Doctor 18/18 and all three
platform exports pass locally. No hosted deployment, provider run or database
change was made.

**Remaining follow-up / owner**

The developer should prepare a focused dependency/lockfile remediation,
verify SDK compatibility and native tooling, then rerun tests/exports/audit.
The critical finding remains unresolved by this documentation change. The
physical SDK54 client must also be checked against current Expo Go support;
a development build is the fallback for an incompatible physical-iPhone client.

---

## 2026-10-05 — AAPL live Debate Stop and Round 2 recovery regressions

**Status:** Corrected locally; one complete real-model AAPL Session passed. A
physical-device, weak-network, and multi-account acceptance pass remains open.

**Symptom and evidence**

An initial live attempt (`93634c30-5dfd-557d-b16c-533024bd1a6d`) failed
safely after a provider stream appeared to finish: final guardrail trimming
could make the published prefix differ from the canonical final content. The
mobile Stop button could disappear when the provider had completed a turn but
the paced reveal still showed only a prefix. Replayed Round 1 terminal SSE
could also close a Round 2 connection. A Round 2 Challenge response timeout
was ambiguous because admission may have committed before the client received
the response. None of these symptoms justifies starting a duplicate Session.

**Mitigation and verification**

Backend commit `0c9fdb2` buffers canonical streamed text before finalization,
keeps prior-generation terminal SSE from ending the active generation, moves
blocking repository calls off the streaming event loop, and loads messages
with their citations in a bounded repository read. Mobile commit `fac5d59`
keeps Stop available for a visible, paced prefix, confirms durable Stop state
before unfreezing, rejects stale generation/Job events, and rereads canonical
state after an ambiguous Challenge submission. Earlier code checks passed 542
backend tests, 122 mobile tests, and TypeScript checking. The completed AAPL
Session `2b6831a2-2f33-5629-bdcc-a403c9ec9c2b` exercised Stop → Explanation
→ user interjection → Continue in both rounds, reached the Final Judge, and
reopened from History with 17 canonical records, including two incomplete
prefixes. The provider-attempt ledger reported 50,380 Debate tokens for this
Session plus one attempt with unknown usage; Explanation usage is separate and
was not measured. This is a controlled run, not a latency or cost baseline.

**Remaining follow-up / owner**

The project owner and developer should repeat Stop and recovery on the target
device, including background/foreground and a weak connection. Implement a
safe V2 in-app model/token readout and reconcile it with the ledger. Do not
claim total model cost from the reported Debate tokens alone.

---

## 2026-10-05 — Citations alone did not verify generated source claims

**Status:** Prospective guard added locally; historical saved text remains
unchanged and source attribution is still conservative, not semantic proof.

**Symptom and evidence**

The completed AAPL run contains an early Round 1 Bull message saved before the
new guard became active; its quoted source wording was not verified against
the linked excerpt. A citation alias identifies supplied evidence, but cannot
by itself establish that an agent's prose or numeric conclusion appears in
that evidence. Some live Explanation calls returned a generic conservative
fallback when the proposed source-specific wording could not be verified.

**Mitigation and verification**

Commit `0c9fdb2` adds streaming source-attribution checks for new Bull, Bear,
and Judge output, checks short direct quotations against the supplied excerpt,
sanitizes old transcript context before using it in new prompts, and makes
Explanation fail safely on unsupported source-specific claims. Commit
`fac5d59` marks earlier Groq v1 records in the mobile transcript. Unit
regressions cover supported quotes, unsupported attributions, and streamed
boundaries. These checks do not retroactively rewrite saved messages.

**Remaining follow-up / owner**

The developer should audit a fresh, fully post-guard live Session and inspect
the actual evidence cards for each consequential assertion. The product owner
should treat old v1 messages as historical test output and review their linked
excerpts before relying on them.

---

## 2026-10-05 — Account workspace and research-screen review

**Status:** Local fixes committed; native multi-account and full visual
acceptance remain open.

**Symptom and evidence**

During sign-out or account switching, outstanding home, stock, Watchlist, and
Debate requests could return after the new account was adopted and repopulate
client state with the former account's data. The stock research panels also
had crowded headers and metadata that could collide at narrow widths; the
Watchlist repeated counts, provenance, and catalog instructions.

**Mitigation and verification**

Commit `12b20c5` clears account workspace state, invalidates outstanding
account-scoped client requests, waits for a fresh home load before rendering,
wraps dense section headings, and shortens Stock Detail and Watchlist copy
while retaining data warnings and accessibility labels. This addresses a
client-state isolation risk; server authorization and RLS remain the canonical
access-control boundary.

**Remaining follow-up / owner**

The developer and product owner should test sign-up/confirmation, sign-out,
two-account switching, Watchlist persistence, and every Stock Detail panel on
the target simulator/device at narrow width. Verify no stale account content
appears during a delayed request. This commit does not establish completion of
that manual acceptance.

---

## 2026-10-05 — Saved Debate detail read reduction needs live measurement

**Status:** Code-level read reduction committed; performance issue still open
until a hosted cold/warm comparison is recorded.

The 2026-09-17 entry below measured 26 serial Supabase reads and 8.210 seconds
for a seven-message Session. Commit `0c9fdb2` replaces the per-message
citation loop with an owner-checked PostgREST embedded message/citation read.
Repository and API regressions check ordering and citation attachment. The
developer should measure cold and warm History reopen after this change and
confirm that the complete owner-scoped transcript is identical; the previous
8.210-second result is historical, not a new timing claim.

---

## 2026-09-17 — Reopening a canonical V2 Debate waits on serial detail reads

**Status:** Open performance issue. No Debate data, model output, or canonical
ordering is incorrect; the current history-to-Debate navigation waits longer
than an interactive reopen should require.

**Scope and verified evidence**

The History action `Open interim assessment` calls `openSavedDebate`, which
awaits `GET /debates/{session_id}` before it sets the screen to the Live Debate
view. It therefore cannot navigate until the entire canonical Session detail is
assembled. This is a read-only operation: it does not call a model or create a
new Debate.

For the saved Round 1 Session inspected on 2026-09-17, the detail contained
seven canonical messages. The current server detail builder performs one
session lookup, two reads to list messages, three reads per message to load
citations with ownership checks, and two reads for the active Job: **26 serial
Supabase REST reads**. A local measurement of the active backend returned the
history list in 1.039 seconds and the selected detail in 8.210 seconds. The
post-navigation AAPL bundle refresh measured 4.133 seconds; it is started
after the screen state is set and is not required to load the saved transcript.
Network timing will vary, so a person seeing 2–3 seconds is consistent with
the same serial-read design.

**Mitigation and verification plan**

Do not replace canonical server data with summary-card data or navigate with a
partially fabricated transcript. The corrective design should reduce the
server detail path to one bounded, ownership-scoped aggregate/RPC read (or a
small fixed number of reads) that returns Session, messages, citations, and
Job together. The client can then either retain its current "load then enter"
behavior with a materially faster response, or enter a clear loading shell
immediately while that canonical response loads.

Before implementing it, add a regression that counts repository transport
calls for a seven-message Session and verifies that an interim transcript,
citations, and Job state remain identical after reopening. Measure cold and
warm reopen latency separately; do not use a model call as a performance test.

---

## 2026-09-17 — V2 Bear turn ended safely before any replayable text

**Status:** The misleading empty-chat-bubble presentation is resolved locally.
The single-attempt live session remains a valid failed-provider test record;
no unverified Bear text was retained or replayed.

**Scope and verified evidence**

In the Expo V2 beta Session `e5fea034-e30c-52b5-99de-a788e1b38df4`, Bull
completed canonically through `openai/gpt-oss-20b` with 1,961 prompt, 253
completion and 2,214 total reported Tokens. Bear was subsequently admitted
and dispatched, but finished as a failed provider attempt after about 18
seconds with unknown usage. The Session and its one-attempt Queue Job both
ended with the safe code `debate_execution_failed`; the durable transcript
contains exactly the completed Bull message.

An authenticated replay of the live process's SSE buffer found Bear's
`turn.started` and terminal failure but zero Bear `turn.delta` events. This
rules out text encoding, reveal pacing, and lost canonical persistence as the
reason for the apparently disappearing Bear chat card. The card was the
intentional zero-content draft created at `turn.started`, which the client
correctly removes at terminal failure. The current safe-error/ledger contract
does not persist the private provider exception or rejected text, so the exact
non-retryable cause cannot be recovered from this terminal Session. Plausible
contract-side causes include an invalid/missing evidence citation, financial
guardrail rejection, an abnormal stream finish, or empty provider content.
It was not classified as a retryable Groq rate-limit/server failure: that path
would have ended as `debate_retry_exhausted`.

**Mitigation and verification**

The mobile transcript now suppresses zero-text drafts while retaining their
underlying state for the existing Stop-before-output control. During that
short interval it says that the agent is preparing its first safe response;
it never shows an empty message that later appears to vanish. A regression
test covers the zero-text versus visible-text boundary. The server continues
to discard incomplete or rejected text rather than promoting it to a canonical
Bear conclusion.

**Remaining follow-up**

Do not mutate or retry this terminal Session. A deliberate fresh live test may
use two Worker attempts only if its additional-model-call budget is accepted;
the current `DEBATE_JOB_MAX_ATTEMPTS=1` setting intentionally chose a single
bounded call. Add a safe, non-content failure-class field (for example,
upstream retryable, guardrail, citation/contract, or stream-finalization) to
the V2 provider-attempt/read model before treating a generic
`debate_execution_failed` as a precise provider diagnosis. Keep raw rejected
text and provider-private error payloads out of the client, logs, and issue
record.

---

## 2026-09-17 — Legacy real-model token usage was hidden and mislabelled as demo usage

**Status:** Legacy display resolved locally; V2 token diagnostics remain an
explicit Beta acceptance and implementation item.

**Scope and verified evidence**

During the local standard-data, single-Groq Legacy Analysis smoke run, the
mobile screen correctly rendered the verified AAPL close, dated FRED/EIA macro
context, Judge output, Bull/Bear claims, and dated evidence freshness. The
analysis response already contains `model_name`, `prompt_tokens`,
`completion_tokens`, and `total_tokens`, but the mobile screen placed this
diagnostic disclosure after both claim cards and labelled its total as "demo
tokens" even when the provider was Groq. This made a successful live-provider
run needlessly difficult to audit from the UI.

The V2 backend preserves provider-attempt model and usage accounting, including
reported versus unknown usage, but the current V2 mobile Session/Message/Job
read types do not expose that ledger. A V2 screen therefore cannot yet present
reliable per-role or Session token diagnostics, despite rendering provider
deltas and canonical messages.

**Mitigation and verification**

Legacy diagnostics now show the actual total, prompt, and completion counts
without describing them as demo usage. A mobile regression test prevents the
misleading label from returning. This changes presentation only and makes no
provider request.

**Remaining follow-up**

Before V2 Beta/device acceptance, extend the safe read-only V2 API/client
contract with provider/model and reported-or-unknown usage fields. Then verify
on a controlled live stream that token diagnostics reconcile with the
provider-attempt ledger and that reveal pacing, canonical completion, Stop,
reconnect, and foreground/background transitions neither reveal hidden text
nor duplicate or reorder text. The active checklist is in
[`wp8l-next-steps.md`](wp8l-next-steps.md).

## 2026-09-12 — Expo SDK 52 is incompatible with the current physical-iPhone Expo Go path

**Status:** Open; Android and simulator workarounds are documented, while a
physical-iPhone Expo Go gate requires an SDK upgrade or an accepted development
build substitution.

**Scope and verified evidence**

The mobile package remains on Expo SDK 52 and React Native 0.76.9. As of this
review, Expo's current download page lists Expo Go for SDK 57. Expo documents
that an unsupported project/client pairing returns “Project is incompatible
with this version of Expo Go,” that version-specific Expo Go clients can be
installed on Android devices and Android/iOS simulators, and that Apple policy
does not permit side-loading an older Expo Go version on a physical iPhone.
The earlier Android-emulator attempt already recorded that this project
resolved an SDK 52 Expo Go client; it did not complete the download and is not
a native-device pass. `expo-doctor` passing 18/18 proves dependency consistency
inside the SDK 52 project, not compatibility with the current App Store client.

**Impact and mitigation**

The root README now states the SDK version before its device instructions and
links the official SDK 52 Android download. An Android physical device can use
a matching client; both platform simulators can use version-specific clients.
If a physical iPhone reports the mismatch, repeatedly restarting Metro or
changing LAN/tunnel settings cannot fix it, and Web review cannot substitute
for the native gate.

**Remaining follow-up**

Record the product owner's acceptance-device platform. For a physical iPhone,
either upgrade the project through the supported Expo SDK sequence and rerun
mobile/typecheck/export/device regression gates, or explicitly replace Expo Go
with a development build in the acceptance plan. This compatibility decision
precedes any claim that the Expo Go physical-device gate passed. Official
references: [Expo Go version tooling and mismatch guidance](https://docs.expo.dev/develop/tools/)
and the [SDK 52 client download](https://expo.dev/go?device=true&platform=android&sdkVersion=52).

## 2026-09-12 — Expo SDK54 remediation resolved the physical-iPhone blocker locally

**Status:** Resolved locally; product-owner iPhone Expo Go acceptance and a
separate Android native regression remain open.

**Scope and verified evidence**

Following the blocker above, the mobile project was upgraded one SDK at a time
(52 → 53 → 54) in mobile baseline `0f70366`. It now uses Expo `54.0.37`, React
Native `0.81.5`, and React `19.1.0`; React Native safe-area usage was migrated
to `react-native-safe-area-context`. Mobile **112** tests, TypeScript, Expo
Doctor **18/18**, and both iOS and Android native exports pass locally. These
checks prove the build/dependency path, not runtime acceptance on a physical
device.

**Impact and mitigation**

The SDK54 App Store Expo Go client is now the planned iPhone acceptance client.
The phone and development computer must be on the same Wi-Fi network; the
reviewer opens Expo Go, chooses **Scan QR code**, and scans the QR code printed
by `npx expo start --lan --clear`. The API URL must use the computer's LAN IP,
not `localhost`. Android can use a matching SDK54 Expo Go client or simulator.
SDK54 mandatory Android edge-to-edge remains a separate runtime boundary:
status/navigation insets, bottom navigation, keyboard avoidance, and back
behavior still need native simulator or available-device review.

**Remaining follow-up**

The product owner must complete the iPhone App Store Expo Go real-device/UI
acceptance. Android edge-to-edge must then be checked in a native simulator or
available device; do not substitute a Web browser or native export for native
runtime evidence. Official references:
[Expo Go version mismatch guidance](https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/),
[Expo SDK upgrade walkthrough](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/),
and the [SDK54 release notes](https://expo.dev/changelog/sdk-54).

## 2026-09-12 — Expo SDK54 npm audit findings are transitive and deferred

**Status:** Recorded; no force-fix or dependency override is approved.

**Scope and verified evidence**

Running `npm audit` for the SDK54 mobile dependency graph reports **18**
findings: **7 moderate**, **11 high**, and **0 critical**. The findings are in
transitive Expo/Metro/config-build tooling rather than application code. npm's
only complete remediation path proposes upgrading Expo to SDK57.

**Impact and mitigation**

For this project, forcing that path would break the current App Store Expo Go
SDK54 target. Do not run `npm audit fix --force` and do not force or override
transitive Expo/Metro versions to silence the report. Metro is used only on a
trusted local network during development; no public Metro endpoint is part of
the release path.

**Remaining follow-up**

Re-evaluate the audit when Expo Go supports the newer SDK target, then upgrade
incrementally and rerun the full mobile/device gates. Until then, retain the
SDK54 target and record these findings as a known tooling-chain limitation.

## 2026-09-12 — Persisted rebuttal point exceeded the next-request domain bound

**Status:** Resolved and verified by a subsequent full two-round run.

**Scope and verified evidence**

Current-SHA Session `820646d0-cb0f-5a2f-8e24-c3ca9529175b` passed Queue
admission and completed five paced Round 1 Turns, then entered the safe
`debate_execution_failed` terminal state before admitting the sixth provider
request. The ledger contains exactly five dispatched/completed attempts, all
with reported usage, totalling 13,366 Tokens and no Worker retry or unknown
usage. The fifth canonical message retained a 334-character server-authored
`rebuttal_point`; `_prepare_turn` projected it unchanged into
`previously_used_points`, whose domain item limit is 300 characters. Request
validation therefore failed before the sixth provider admission.

The first verifier failure report correctly stopped at the terminal SSE event,
but displayed zero observed requests because it only read the provider ledger
after a successful phase terminal. The hosted ledger, not that incomplete
failure-report field, is the authoritative usage evidence above.

**Mitigation and verification**

`19b9d85` bounds the projection at the orchestrator boundary. It preserves the
original canonical metadata for audit while supplying at most 300 characters
per prior point to both synchronous and streaming Turn requests. Its regression
uses legal 500-character provider points, completes all six Round 1 Turns and
checks both the preserved canonical value and bounded later requests.
`901cddb` makes the verifier re-read and safely summarize provider attempts
after a workflow failure, including admitted/dispatched counts, reported and
unknown usage, outcomes and budget state. The full backend suite passes 516
tests with one existing Starlette warning. An independent Luna 5.6 Extra High
read-only audit confirmed the shared orchestrator projection as the smallest
safe fix; neither fix made a provider call.

**Remaining follow-up**

Do not represent the failed Session as a Round 1 or full-flow pass; retain its
13,366 reported Tokens in cumulative accounting. Session
`ee8409eb-f415-54b3-892e-d47d85516ae4` on later SHA `64c1c6c` crossed the
previous failure point and passed the full 12-request, two-Judge, two-round
verifier with no retry or unknown usage. This issue no longer blocks Expo Go.

## 2026-09-11 — Late Round 2 Turn Prompt lacked free-tier margin

**Status:** Resolved for the bounded AAPL acceptance profile.

**Scope and verified evidence**

After bounding the Judge, a no-provider-call reconstruction of retained Session
`0fc62829-dd7b-56c9-a766-0e2e1b3092db` found that the six-message Round 2
opening Turn Prompt still contained 24,954 characters and a late-Round-2
projection reached 31,127. This had not yet failed a provider request, but left
insufficient input/output margin under the same 8K TPM free-provider envelope
that had already affected the full run.

**Mitigation and verification**

`7f6a4da` caps the Turn projection at six evidence items, twelve factor
observations, ten transcript messages, six interrupted prefixes and eight prior
points; it also bounds individual text fields and lowers the default completion
cap from 1,600 to 800 Tokens. The same retained Session now reconstructs to
12,813 characters for the Round 2 opening and 16,289 for a twelve-message late
Round 2 projection. A worst-input unit test includes eight source evidence
items, 51 factors, 14 long transcript messages, six maximum-length interrupted
prefixes, 30 prior points and maximum question/interjection text. The full
backend suite passes 515 tests with one existing Starlette warning. No Groq
request or generated-text logging was used for this verification.

**Remaining follow-up**

The character projection is calibrated to the retained English AAPL inputs; it
is not a universal tokenizer proof for arbitrary high-Unicode content. Session
`ee8409eb-f415-54b3-892e-d47d85516ae4` subsequently completed all twelve
requests, including both bounded Judges and every Round 2 Turn, with 39,269
reported Tokens. Keep the same bounds and 61-second pacing during Expo Go.

## 2026-09-11 — Full Live Debate exceeded the Groq free request envelope

**Status:** Resolved for the bounded AAPL acceptance profile.

**Scope and verified evidence**

Current-SHA Session `eb564e13-a53f-5b59-af47-4088d51322e1` completed two
Turn requests with 9,175 reported Tokens in 29 seconds, then its third Turn was
rejected 0.3 seconds after dispatch as a retryable upstream failure. Groq's
current free-plan table lists `openai/gpt-oss-20b` at 8K TPM and states that
limits apply at organization level. A later paced Session
`0fc62829-dd7b-56c9-a766-0e2e1b3092db` completed all six Round 1 Turns with
31,155 reported Tokens and valid citations, proving that serialized pacing
removed the per-minute failure. Its Interim Judge was then rejected before any
output. Reconstructing that request without calling the provider measured a
34,391-character Judge prompt, consistent with a non-retryable oversized
request; the failed attempt has unknown usage and is not represented as zero.

**Mitigation and verification**

`46eb16c` adds a shared monotonic provider pacer and defaults configured live
Groq sessions to one request start every 61 seconds. It rechecks the active
generation after waiting and before admission, so Stop cannot release a stale
request. `399e6fe` replaces the Judge's unbounded factor dumps with bounded,
selected fields, caps evidence/transcript projections, lowers the 120-word
Judge completion ceiling to 800 Tokens, and repeats the citation contract after
the frozen data. The exact failed-session reconstruction falls from 34,391 to
10,827 prompt characters, a 68.5% reduction. The backend suite passes 513
tests. See Groq's official [rate-limit table](https://console.groq.com/docs/rate-limits)
and [HTTP error reference](https://console.groq.com/docs/errors).

**Remaining follow-up**

The later current-SHA Session `ee8409eb-f415-54b3-892e-d47d85516ae4`
completed all twelve attempts with one Worker attempt per phase, both Judges,
40 citation links, canonical reload and SSE terminal checks. Its Bull, Bear and
Judge totals were 15,851, 16,808 and 6,610 Tokens respectively, all on
`openai/gpt-oss-20b`. Continue to apply pacing and explicit daily accounting;
the remaining owner gate is Expo Go, not another model-side rerun.

## 2026-09-11 — Live Bear prefix lacked the required evidence citation

**Status:** Resolved for the subsequent six-Turn live sequence.

**Scope and verified evidence**

Session `b5d2d2f3-ee6d-53af-896c-0d0baea88027` completed one Bull Turn, then
the Bear stream exposed a durable 911-character prefix but failed final
validation. The prefix contained no citation token despite six available
evidence aliases; it contained no invalid alias syntax, out-of-range alias or
forbidden financial phrase. The failed provider attempt retained unknown usage
and no canonical Bear message was written. The verifier initially consumed all
reconnects because it did not treat `session.failed` as a terminal failure.

**Mitigation and verification**

`70b8ce3` repeats a strict response contract after the untrusted frozen context,
requires each evidence-bearing paragraph to begin with relevant exact aliases,
and reduces Turn sampling temperature to 0.2 without fabricating citations.
The verifier now stops immediately on `session.failed` or
`session.cancelled` and reports only the safe terminal code. In the later paced
Session, all six Bull/Bear Turns completed with two to four valid citations and
no invalid citation or forbidden phrase. The full backend suite passed before
and after the change.

**Remaining follow-up**

The next full run must still prove both bounded Judge outputs and Round 2. Keep
rejected text out of documentation and preserve unknown usage in the attempt
ledger.

## 2026-09-11 — First current-SHA Live run exposed SSE ownership and ambiguous admission timeout

**Status:** Mitigated locally and in hosted SQL; one bounded verification rerun remains.

**Scope and verified evidence**

The current-SHA verifier admitted Session
`bb222d34-5d31-54eb-b0d0-a503f58304ee` with Queue `202`, then raised
`httpx.StreamClosed` because it returned an SSE response from a temporary
context manager that immediately owned and closed that response. The Worker
continued independently. It completed two real Groq Turn requests, then a third
provider admission committed in Supabase but its HTTP response exceeded the
repository's 10-second transport window. That attempt remained
`admitted`, was never dispatched, retained unknown usage, and the one-attempt
Job ended safely as failed. Exactly two provider calls reported 9,093 total
Tokens; the failed Session recorded three admission rows and did not retry.

**Mitigation and verification**

The verifier now sends a streaming request whose response remains caller-owned
until explicit close and treats midstream `httpx.StreamError` as a bounded
reconnect condition. Persistence now retries one transport failure only for
exactly replayable checkpoint, provider-ledger and canonical-message writes.
Dispatch replay accepts only the same attempt id and timestamp; a changed
timestamp remains an HTTP 409 conflict. Hosted migration
`20260911_provider_attempt_transport_replay.sql` is applied, and the isolated
PostgreSQL suite plus focused repository/verifier tests pass. The Supabase
security advisor shows no new warning from this migration.

**Remaining follow-up**

Run the full backend suite, commit the mitigation, restart the single-process
acceptance runtime on that SHA, then execute one new twelve-request run. Record
the failed Session and both completed calls in final accounting rather than
treating the first run as a pass or silently discarding its usage.

## 2026-09-11 — Hosted interruption RPCs exposed retry and Queue privilege defects

**Status:** Resolved and verified on the hosted Supabase project.

**Scope and verified evidence**

The disposable hosted interruption verifier twice timed out on a deliberate
wrong-owner Stop. The RPC returned SQLSTATE `40001` for an application-level
optimistic conflict; PostgREST 14 treats that code as a transient serialization
failure and retries it. After the conflict code was corrected, Continue reached
its Queue write but returned `403` because the function called `pgmq.send`
without the Queue RPCs' service-only `SECURITY DEFINER` boundary.

**Mitigation and verification**

The source migrations now use `PT409` for application conflicts. Corrective
migration `20260911_postgrest_conflict_status.sql` updates already-migrated
projects, and `20260911_continue_queue_security.sql` gives only `service_role`
the narrowly scoped Continue execution path. The hosted project contains all
three interruption migrations, exposes no listed Debate RPC containing
`40001`, and the full disposable Stop, restart recovery, interjection, Continue,
before-output Stop, ownership, idempotency and cleanup verifier passes. The
backend suite passes 501 tests and the isolated PostgreSQL migration suite
passes. Supabase documents the retry behaviour in its
[PostgREST custom error-code troubleshooting guide](https://supabase.com/docs/guides/troubleshooting/high-cpu-and-infinite-transaction-retries-when-using-custom-error-codes-in-rpc-functions-77326b).

**Remaining follow-up**

Hosted sequential draft checkpoints measured about 212 ms at p50 and 309 ms at
p95. Reduce the number of synchronous round trips with bounded server-side
delta batching while preserving the invariant that the UI only receives text
after its cumulative prefix is durable.

## 2026-09-11 — Virtualenv console scripts retained the former workspace path

**Status:** Mitigated; environment rebuild remains optional.

**Scope and verified evidence**

After the repository moved from the former `B学期576` path to
`BSemester576`, invoking `backend/.venv/bin/pytest` failed before test
collection because its generated launcher still referenced the former absolute
Python path. The interpreter at `backend/.venv/bin/python` remains usable, and
running pytest through `python -m pytest` succeeds.

**Mitigation and follow-up**

Development and verification commands must use
`backend/.venv/bin/python -m pytest` while this virtual environment is retained.
Recreate `backend/.venv` from the committed dependency files if other generated
console scripts prove unusable; do not treat this launcher failure as a product
test failure.

---

## 2026-09-11 — Live Queue verifier review found false-positive acceptance paths

**Status:** Resolved locally in `63406d4`; hosted/live execution remains open.

**Scope and verified evidence**

The paused verifier initially allowed an async deterministic provider to satisfy
the “live” metadata check, accepted a failed-only provider-attempt row as coverage
for a canonical completed message, omitted the observed server SHA from its
report, and did not require per-message delta/citation events or a complete
current-data snapshot. Its reconnect test also combined an initial connection
failure and a deliberate short stream inside a one-reconnect limit, so the test
failed before any external request was made.

**Mitigation and verification**

`63406d4` requires the expected live Turn and Judge provider identities, at
least one successful positive-Token attempt for every canonical model message,
per-message started/delta/citation/completed SSE evidence, the actual server SHA,
and a non-content AAPL snapshot summary covering prices, quote, news/filing,
seven macro series and SEC facts. The reconnect fixture now separates a passing
two-reconnect case from the bounded failure case. Twelve focused tests and all
492 backend tests pass; no provider or market-data request was made by this
review.

**Remaining follow-up**

Apply and verify the interruption migration on the hosted Supabase project,
refresh only sources that fail the current preflight, and execute exactly one
bounded current-SHA run with the dedicated acceptance user. Record the Session
ID, provider attempt/Token summary and any unknown usage without storing the
generated transcript or credentials.

---

## 2026-09-11 — Independent staging removed from the project release scope

**Status:** Scope decision recorded; active plans synchronized.

**Decision and impact**

The product owner confirmed that this is not a commercial release and does not
require a separately deployed test frontend. Phase 8/9 will not create a second
Render environment and will not use the Render static Web frontend as an
acceptance gate. Expo Go remains the product UI/device acceptance surface.

The replacement release check deploys the accepted commit to the existing
Render API, verifies `/health.build_sha`, authentication, the stock/Queue/SSE
smoke path, migration compatibility, cold start/restart behaviour, and a
concrete rollback target with a dedicated test account. Older issue entries and
verification notes that require same-SHA staging are historical records and are
superseded by this decision; they have not been rewritten because this log is
append-only.

**Remaining follow-up**

Review and commit the paused Live Queue verifier, complete hosted Supabase and
current-data/model checks, perform Expo Go acceptance, then run the existing
Render backend release and rollback gate. No extra Render service or staging
payment decision remains in the active route.

---

## 2026-09-11 — Live acceptance could not enforce its call budget or prove the running SHA

**Status:** Partially resolved locally; paused before hosted/live verification.

**Scope and verified evidence**

- The planned two-round Groq run has a nominal cost of twelve provider calls.
  The Worker owned retry dispatch, so a client verifier could notice a retry
  only after it happened; a Round 2 retry could exceed the nominal budget.
- `/health` did not expose an immutable source revision, so a successful Live
  run could not prove which backend SHA produced it.
- Macro ingestion refreshed all six FRED series plus WTI together. It could not
  refresh a single stale WTI series without spending seven upstream calls.
- No existing verifier covered Queue `202`, resumable SSE, both rounds, both
  Judges, citations, reload and provider-attempt accounting in one run.

**Local mitigation**

- `38495e3` adds `DEBATE_JOB_MAX_ATTEMPTS`; acceptance can set it to `1` so the
  Worker cannot automatically repeat a stage.
- `cf8b9e7` adds validated `APP_BUILD_SHA` and exposes `build_sha` through
  `/health` without deriving it at runtime.
- `583610c` adds a validated selected-series macro refresh and proves that
  `--series wti_spot` constructs only EIA and performs one provider request.
- A mocked full-flow verifier and test now exist as uncommitted files. Its
  first test pass is not acceptance evidence, and its independent review was
  interrupted by the requested pause.

**Remaining follow-up**

Review and commit the verifier, require the expected build SHA and
`max_attempts=1`, apply/verify the interruption migration in the hosted test
environment, then perform only the freshness calls required by the current
AAPL snapshot. Record failed calls and unknown Token usage. No external data or
model call was made while diagnosing or mitigating this issue.

---

## 2026-09-11 — Interruption contracts diverged across server, stream and mobile UI

**Status:** Resolved locally; hosted and Expo Go confirmation remain open.

**Scope and verified evidence**

- The first mobile interjection/Continue integration sent the interrupted
  message's old generation while the server correctly required the new
  waiting `active_generation_id`; normal saves would have returned a conflict.
- When provider text was received but reveal pacing still displayed an empty
  prefix, Stop selected the before-output RPC. The server could already have a
  draft checkpoint and reject that request.
- End could return `cancel_requested` and then stop the local stream, leaving
  the screen unable to observe the terminal `cancelled` state.
- During integration, the backend temporarily required a saved interjection
  before End while the UI offered End as an independent action.

**Local mitigation and verification**

- `69368de` and `2478804` align Interjection/Continue on the post-Stop waiting
  generation while retaining the old generation on the frozen message.
- Stop now distinguishes received provider text from rendered text and uses
  the regular prefix RPC when a draft exists, including an empty visible
  prefix. Before-output Stop remains for a generation with no draft.
- End is available directly after a confirmed Stop; only Continue requires a
  saved viewpoint. The client reconnects when End returns a nonterminal state.
- Stable generation-scoped keys cover retry/duplicate actions. Local gates pass
  480 backend tests, 111 mobile tests, TypeScript and isolated PostgreSQL.

**Remaining follow-up**

Verify weak-network timeout, two-client races, background/foreground,
kill/reopen, Judge interruption, History reload and the complete
Stop/interjection/Continue/End flow against hosted Queue state in Expo Go.

---

## 2026-09-08 — Active Debate conflict has no local recovery affordance

**Status:** Implemented locally / awaiting product-owner visual confirmation.

**Scope and verified evidence**

- From the stock page, tapping Debate does send the request. The local backend
  records repeated `POST /debates` responses as `409 Conflict` because the test
  user already has an unfinished Debate in `awaiting_user`.
- The one-active-Debate admission rule is functioning as intended. This is not
  a Debate-generation failure and is unrelated to the V2 state proxy.
- At discovery, the frontend placed the error only in the stock page's
  top-level feedback area. Because the Debate action is at the bottom of the
  page, the user could be looking at the action while missing the error; there
  was also no nearby action to open the existing Debate or navigate to History.

**Impact**

The Debate action appears unresponsive when an active Debate exists, even
though the backend is correctly preventing a second unfinished Debate.

**Required follow-up and owner**

Commit `0e7c813` implements the recovery interaction locally: it preserves the
API conflict status, protects against synchronous duplicate submissions, adds a
recovery card near the Debate action, and provides an action to open the current
Debate or navigate to History. The latest local mobile gate reports 72 passing
tests, with typecheck and Web export passing. Commit `8c9278c` adds the V2
transient proxy for reconnect, retry, cancel, and failure; its focused suite
reports 15 passing tests.

The remaining follow-up is product-owner visual/page confirmation. Engineering
owns the reproducible entry point, code changes, focused automated evidence,
and verification record; the product owner can use the concise checklist and
report observations back to engineering. Xcode/native simulator, physical
device, and final visual acceptance remain outstanding.

Restarting the local `review_fixture` to clear in-memory state or opening the
existing Debate from History are temporary review workarounds only.

---

## 2026-09-06 — Data and release integrity gaps block current UI acceptance

**Status:** Open; release and Phase 8 remediation required.

**Scope and verified evidence**

- The local implementation is approximately 150 commits ahead of the remote
  `main` branch, so the public deployment is not a reliable representation of
  the current working tree. The public API returns `404` for the current
  `GET /stocks/{ticker}/bundle` contract.
- The deployed AAPL daily cache is stale; the latest observed daily close is
  2026-08-19 at the time of this audit.
- The daily price-refresh workflow can still exit successfully after its
  update step fails, allowing a failed refresh to appear green to the release
  process.
- Frontend and backend RSI/volatility calculations do not currently share one
  verified calculation contract, so displayed values and plotted series can
  diverge.
- The current `verified` history check verifies the final source identity but
  does not require the minimum number of valid historical observations.

**Impact**

The public demo can be stale or serve an older API surface while local code
appears healthy. A reviewer cannot distinguish a design/chart defect from a
deployment mismatch or an incomplete data snapshot, and a green refresh job
does not prove that current market data was written.

**Required remediation**

1. Establish a single release SHA and expose the current `/bundle` contract in
   staging before public-demo promotion.
2. Make refresh failures fail the workflow, record freshness, and add a
   post-write verification for the expected close date and row count.
3. Centralize RSI/volatility formulas and test frontend/backend parity against
   fixed fixtures.
4. Require both source provenance and minimum valid history length for
   `verified` status; represent stale or insufficient data explicitly.
5. Add a clearly labelled `review_fixture` for local visual/chart/Debate review
   so simulated data is inspectable without being presented as market data.

**Owner and follow-up**

The data/release workstream owns items 1–4; the Phase 8 UI workstream owns item
5. Close this entry only after staging same-SHA smoke tests, refresh-failure
verification, indicator parity tests, and the visual acceptance evidence are
recorded. No credentials or private configuration are included in this entry.

**2026-09-07 local mitigation update**

WP1 now implements items 2–4 locally: failed and non-advancing daily refreshes
exit nonzero, Supabase reads the newest rather than oldest limited window,
backend/client indicators share a golden-vector contract, and complete-history
status requires 50 valid ordered unique completed closes plus trusted
provenance. The complete backend and mobile gates pass. The issue remains open
until an authorized live refresh proves the hosted AAPL cache advances and
same-SHA staging plus visual review close items 1 and 5. WP2's deterministic
`review_fixture` implementation and no-outbound checks are now recorded; its
responsive/device/product-owner acceptance remains open.

---

## 2026-08-28 — Local Settings representation exposed configured credentials

**Status:** Code mitigation complete; owner credential rotation required.

**Scope and evidence**

- A newly added Redis configuration assertion failed while evaluating
  `repr(Settings(...))`.
- Pytest's assertion introspection printed the Settings representation into the
  local task output. Because existing credential fields still used Pydantic's
  default `repr=True`, the representation included values loaded from the
  ignored local `.env` file.
- No credential was written to a tracked repository file or committed to Git.
  The affected task/test output must nevertheless be treated as an exposure.

**Immediate mitigation**

- Commit `7058acd` marks Redis URLs, Supabase keys/test accounts, provider keys,
  tokens, and the SEC contact identity `repr=False`.
- The regression test now inspects representation field metadata rather than
  rendering a populated Settings object.
- The focused test and the complete 280-test backend suite pass without
  printing configuration values.

**Required owner action**

- Rotate every currently configured server-side secret/provider credential in
  the local `.env`, including the Supabase server secret, disposable RLS-user
  passwords, and configured market/model/data-provider keys or tokens.
- Replace the SEC contact address if its disclosure is not acceptable.
- Update the local `.env` and the corresponding GitHub/Render secret-manager
  values. Do not paste replacement values into chat, documentation, terminal
  output, or Git.
- After rotation, record only the completion date here and mark the issue
  resolved.

---

## 2026-08-27 — Direct-database password rotation lacks recorded verification

**Status:** Open owner verification; no current API-path impact.

**Known evidence**

- The live-services setup record states that the initially generated direct
  Postgres password was exposed during setup.
- The current application uses Supabase project-scoped API keys and does not
  require that direct-database password for its normal mobile/API paths.
- No repository record currently proves that the direct-database password was
  rotated.

**Required action**

- Before enabling any direct Postgres connection, rotate the password in
  Supabase Database Settings.
- Record only the completion date. Do not record the old or replacement value,
  screenshots, or connection strings.
- Once verified, mark this entry resolved and update the credential-hygiene
  note in [`../setup/live-services.md`](../setup/live-services.md).

---

## 2026-08-21 — Debate view crashed on timestamp-formatted evidence dates

**Status:** Resolved and production-verified.

**Symptom and impact**

- Pressing **Run analysis** could produce `RangeError: Invalid time value` and
  leave the web Debate view blank.
- The error was raised while rendering dated citations, not while generating
  Bull, Bear, or Judge content.

**Verified evidence and diagnosis**

- A read-only production response-shape audit confirmed that saved Debate
  evidence uses complete ISO 8601 `published_at` timestamps, while macro
  `observation_date` values are date-only.
- The mobile `formatMarketDate` helper appended `T12:00:00Z` to every input.
  This converted a valid evidence timestamp into an invalid string with two
  time components, and `Intl.DateTimeFormat` threw during the citation map.
- The macro context itself is available to real Groq/Gemini provider prompts.
  Production currently uses the deterministic demo provider, whose Bull/Bear
  text had not previously made the same dated background explicit.

**Remediation**

- `853527a` separates date formatting into a defensive helper. It parses
  `YYYY-MM-DD` market dates and complete ISO timestamps correctly, and shows a
  safe unavailable label instead of crashing for missing or malformed values.
- `1d7ef8b` adds the complete close-date-bounded macro background to demo Bull
  and Bear text with explicit non-causation language. It remains background,
  not claim evidence, and does not weaken the no-current-news safety cap.
- Full backend tests (78), mobile TypeScript checks, and Web export pass before
  deployment.

**Production verification**

- Render deployed the updated backend and a new static Web bundle. The bundle
  contains the safe date fallback instead of the former unconditional date
  formatting path.
- An isolated test-account AAPL Debate returned `201` with the expected CORS
  header. Its response contained six complete ISO evidence timestamps and
  seven close-date-bounded macro observations.
- Both demo Bull and Bear claims contained the dated macro-background statement
  and its explicit non-causation boundary. This confirms the data reaches the
  returned Debate content as well as the immutable snapshot.

**Related code**

- `apps/mobile/src/dateFormat.ts`
- `apps/mobile/App.tsx`
- `backend/app/services/analysis.py`

---

## 2026-08-21 — Legacy analysis history causes production `/analysis` 500

**Status:** Resolved and production-verified.

**Symptom and impact**

- The production web app reported a CORS failure while requesting `GET
  /analysis`, accompanied by an HTTP `500` response.
- The home screen cannot reliably load a signed-in user's saved analysis
  history while an incompatible historical record is present.

**Verified evidence**

- Production CORS is correctly configured for
  `https://ai-bull-vs-bear.onrender.com`: an `OPTIONS /analysis` preflight and
  an unauthenticated `GET /analysis` both return the expected
  `Access-Control-Allow-Origin` response header.
- A read-only, aggregate-only audit of stored `agent_outputs` found six saved
  `response` records. Five predate the immutable analysis-snapshot contract and
  omit the now-required `snapshot` object; one current-format record parses.
- `SupabaseStore.list_analyses()` calls `AnalysisResponse.model_validate()` for
  every stored response without handling validation failures. A legacy record
  therefore raises an unhandled validation error and turns the endpoint into a
  `500`.
- The browser's CORS message is secondary: FastAPI's outer server-error path
  generates that unhandled `500` outside the currently added CORS middleware,
  so the error response has no CORS header for the browser to read.

**Data-integrity decision**

Do not fabricate a current-price snapshot for historical analyses and do not
delete the old rows. Those records lack the immutable market-close/evidence
metadata required to represent them as equivalent to a current-format Debate.

**Required remediation**

1. Make analysis-history reads backward compatible: skip or explicitly label
   non-reproducible legacy records instead of letting one invalid row fail the
   entire list. Apply the same handling to a direct request for a legacy record.
2. Wrap the whole FastAPI application with CORS so that unexpected `500`
   responses still return the permitted-origin header and expose a readable API
   error rather than a misleading browser-only CORS failure.
3. Add regression tests containing a pre-snapshot stored response and verify
   that valid current-format history remains accessible.

**Local remediation completed**

- `b53dc6f` makes persisted-history parsing tolerant of legacy records. They
  remain stored but are omitted from current-format history and direct legacy
  lookups return no current-format response.
- `76e9464` wraps the complete FastAPI application in CORS middleware, so an
  unexpected server error still returns the permitted-origin header.
- The new legacy-history and unexpected-error CORS regression tests pass; the
  full backend suite passes 78 tests.

**Production verification**

- Render auto-deployed commit `039caf0` and marked the service live.
- Public `/health` returns `200`.
- An authenticated, origin-bearing production request to `/analysis` returns
  `200` and the expected `Access-Control-Allow-Origin` value. It returns the
  one current-format stored record; the five incompatible legacy records remain
  intact in storage and do not interrupt the response.

**Related code**

- `backend/app/services/supabase_store.py`
- `backend/app/main.py`
- [`reports/project-week-06.md`](reports/project-week-06.md)

---

## 2026-08-21 — Render deployment health-check timeout

**Status:** Resolved by redeploy; root cause not proven.

**Symptom and impact**

- Render marked deployment commit `1e15a7d` (`feat(analysis): snapshot
  non-causal macro context`) as failed after its internal health check timed
  out at `/health`.
- The previous live release remained serving, so the immutable macro snapshot
  feature and later main-branch changes were not yet available in production.

**Verified evidence**

- The failed Render deployment completed its image build, then timed out during
  the deploy/health-check phase. Its visible logs did not contain a Python
  traceback or Uvicorn startup failure.
- A local production-style launch of the same FastAPI application started
  successfully and returned `200` from `/health`.
- A user-approved manual deployment of latest `main` (commit `18f7e45`)
  subsequently started Uvicorn, completed application startup, received
  repeated Render `GET /health` responses with `200 OK`, and reached the
  Render `live` state.
- An independent public check confirmed `/health` and confirmed that the
  production OpenAPI `AnalysisSnapshot` schema includes `macro_context`.

**Diagnosis**

The available evidence is more consistent with a transient Render deployment
or health-check transition failure than with a reproducible application-start
defect. This is an inference, not a confirmed platform root cause: retain the
failed deployment logs if the problem recurs.

**Mitigation and verification**

- Performed one normal manual “Deploy latest commit” action only; no environment
  variables, service settings, or build cache were changed.
- Render logs verified a healthy Uvicorn process and successful health checks.
- Public verification: `https://ai-bull-vs-bear-api.onrender.com/health`.

**Follow-up**

- If another deploy times out, capture its full runtime logs and compare its
  startup timestamp, bound port, and `/health` request records before changing
  code or clearing the build cache.
- Add an uptime/health monitor during release preparation (Week 5) so an
  unavailable production API is detected outside the deployment dashboard.

**Related records**

- [`reports/project-week-06.md`](reports/project-week-06.md)
- [`current-status.md`](current-status.md)
