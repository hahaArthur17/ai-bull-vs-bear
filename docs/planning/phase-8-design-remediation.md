# Phase 8 Design Remediation Execution Plan

**Status:** In progress  
**Last updated:** 2026-09-08
**Parent plan:** [`portfolio-implementation-plan.md`](portfolio-implementation-plan.md)  
**Visual reference:** [`../../prototype.html`](../../prototype.html)

## 1. Authority and purpose

This document is the canonical portfolio plan's phase-specific execution
breakdown for Phase 8. It adds implementation detail to the Phase 8 checklist
in `portfolio-implementation-plan.md`; it does not establish a parallel product
plan, replace the portfolio phase order, or move Phase 9 work into Phase 8.

Phase 8 was re-baselined because the earlier implementation preserved and
tested many product states but did not match the accepted visual direction or
the desired Debate interaction. The project is therefore not one periodic
device check away from completion. The existing UI is a functional foundation,
not an approved final presentation.

## 2. Accepted product direction

These decisions are fixed for this phase unless the product owner explicitly
changes them and the parent plan is updated in the same change.

### 2.1 Global visual language

- `prototype.html` is the visual reference for the whole product, not only the
  Debate screen.
- Use a deep navy/charcoal shell, layered blue surfaces, high-contrast light
  text, restrained technology accents, Bull green/teal, Bear red/pink, and a
  neutral Judge treatment. Colour never carries meaning alone.
- Reuse the prototype's density, typography hierarchy, floating navigation,
  compact metadata, purposeful hover/focus treatment, and restrained motion.
- Adapt the reference responsively instead of reproducing its fixed mobile
  frame. Desktop must use available space without turning into a stretched
  phone layout.
- Existing accessibility, loading, empty, error, stale, retry, cancellation,
  reconnect, and coverage states remain requirements even when they are absent
  from the prototype.

### 2.2 Debate hierarchy

- V2 is the target experience. Legacy Debate remains available only as a
  clearly labelled fallback until V2 passes the production rollout gate.
- Debate is one chronological chat transcript, not a stack of full-width agent
  cards and not two independent equal-height columns.
- Bull messages align left and Bear messages align right while preserving the
  exact round/exchange order. On narrow screens, the bubbles keep a modest
  left/right offset without compressing readable text.
- Interim Judge and Final Judge summaries are horizontally centred. Final Judge
  is the last and strongest transcript conclusion; Interim Judge is visibly
  provisional.
- User Challenge is a distinct centred intervention, not a Bull/Bear message.
- Every completed agent message distinguishes the argument from facts used,
  interpretation, and uncertainty. Evidence is expandable and shows the source,
  date, freshness, supporting span, and safe source link or identifier.
- Streaming drafts must look temporary. Persisted messages must look canonical.
  Auto-scroll occurs only when the reader is already near the latest message;
  otherwise show a new-message affordance.

### 2.3 Honest data review

- `review_fixture` is a deterministic local/preview mode for reviewing every
  chart, technical signal, freshness state, and Debate interaction without
  credentials or provider calls.
- Every fixture surface permanently displays wording equivalent to
  `SIMULATED DATA · LOCAL UI REVIEW · NOT A MARKET PRICE`. The provenance
  must survive navigation, screenshots, and responsive layouts.
- Production may show verified fresh data, verified stale historical data with
  a warning, or an unavailable state. It must never fabricate a quote, history,
  indicator, fact, citation, or Debate evidence to fill missing live data.
- The existing generic `demo_fallback` must not blur a deliberate UI fixture
  with a production-provider failure. Compatibility may remain internally, but
  the user-facing provenance states must be explicit.

### 2.4 Controlled Live Acceptance

- The approved UI is tested first with deterministic fixtures, then with a
  bounded `standard`-mode AAPL session using real provider data and model calls.
  Live acceptance is a separate gate; switching configuration flags is not
  evidence that it passed.
- “Latest price” has two explicit meanings: a latest provider quote with a
  timestamp, and the latest completed daily close used by historical charts and
  technical indicators. Never insert an intraday quote into the daily-close
  series or label a completed close as real-time.
- Every Debate freezes one immutable, displayed snapshot. A quote, close,
  evidence item, filing fact, or macro observation that arrives later belongs to
  a new Session rather than silently changing an active transcript.
- Provider deltas and visual pacing are separate concerns. The client buffers
  ordered deltas and reveals English by word or CJK text by grapheme at a
  controlled pace; a fast provider must not cause a completed message to appear
  all at once.
- `Stop here` means immediate visual and generation interruption, no later
  agent Turn, preservation of only the validated revealed prefix as explicitly
  incomplete, and a user interjection before any optional continuation. It does
  not mean “finish the current response first.”

## 3. Functional preservation contract

Before redesign work begins, record characterization evidence for this list.
The checked state below means the behaviour is mapped in
[`phase-8-preservation-matrix.md`](phase-8-preservation-matrix.md); it does not
mean its final visual or device acceptance has passed. Every later package must
prove that its touched behaviours still work.

- [x] Authentication: sign in, sign up, validation, disabled/submitting,
  failure, confirmation, sign out, and session restore.
- [x] Discovery: debounced catalog search, no-result/failure recovery, company
  identity, exchange/sector metadata, and coverage status.
- [x] Watchlist: add/remove, persistence, empty state, and `catalog_only`
  support without triggering market or model calls.
- [x] Stock workspace: bundle loading/failure, current quote, provenance,
  freshness, warnings, watchlist action, and `catalog_only` boundary.
- [x] Technical exploration: 1M/3M daily and 6M/1Y weekly price ranges, moving
  averages, RSI, MACD, volume, volatility, textual summaries, and unavailable
  states.
- [x] Macro exploration: all seven dated macro series and their source/freshness
  presentation.
- [x] Evidence and Examination: partial/missing evidence, citation metadata,
  claim selection, loading, result, and failure.
- [x] V2 Debate: queued, running, streaming draft, persisted turn, retry delay,
  failed, cancelled, reconnect, `awaiting_user`, Round 2, and completed states.
- [x] Debate semantics: six Round 1 Bull/Bear turns, Interim Judge, one durable
  Challenge, four Round 2 turns, Final Judge, mutually aware rebuttals, and
  citation constraints.
- [x] Explanation: exact-term selection, loading/result/error, read-only
  behaviour, and no Debate state mutation.
- [x] History: legacy analysis, active V2 session, Interim/Final distinction,
  reopening the correct ticker, empty state, and load failure.
- [x] About/diagnostics: product guidance, progressive technical disclosure,
  health status, and safe error wording.
- [x] Cross-cutting: responsive navigation, keyboard focus, screen-reader
  labels/status, 44px targets, 200% zoom, reduced motion, and no horizontal page
  overflow.
- [x] Legacy Debate remains a labelled fallback and its existing synchronous
  path continues to work until a deliberate V2 production rollout.

No item may be removed because it is visually inconvenient. If implementation
shows that an item should leave scope, record the product decision in the parent
plan before changing code.

## 4. Data-integrity prerequisites

These gates precede subjective chart and Debate approval. A polished screen
cannot compensate for ambiguous or inconsistent input data.

1. **One indicator contract.** Document and test one canonical formula,
   period, warm-up, rounding, null-handling, ordering, and annualisation rule for
   price change, MA20/MA50, RSI, MACD, volume, and volatility. Backend responses
   and client summaries must not compute contradictory values.
2. **Verified history.** A complete technical view requires at least 50 valid,
   chronological, unique completed-close records with explicit provenance.
   Individual visuals degrade by their real mathematical minimum rather than a
   single all-or-nothing UI switch; the price line may render with sufficient
   points even when MA50 is unavailable.
3. **Honest provenance.** Distinguish `live_fresh`, `live_stale`,
   `review_fixture`, and `unavailable`. A latest quote is not evidence of
   verified historical coverage.
4. **Refresh failure is failure.** Daily-price refresh commands and their GitHub
   workflow must exit nonzero when ingestion, validation, or persistence fails.
   A green workflow must mean the expected cache was actually refreshed or an
   explicitly tested no-op condition occurred.
5. **Stale recovery.** Reproduce the stale AAPL condition, repair the refresh
   path, verify the newest completed trading close and record count, and confirm
   that stale warning/refresh recovery behaviour is visible without exposing
   credentials.
6. **Quote/close separation.** Verify the Finnhub quote timestamp/source and the
   newest Alpha Vantage completed-close date independently. Market-closed,
   weekend, holiday, delayed, stale, and provider-unavailable cases must retain
   honest labels; “today” is never inferred from the workstation date alone.
7. **Debate snapshot parity.** Record exactly which quote, close, evidence,
   filing facts, macro observations, and indicator values enter the model
   snapshot. The stock page and Debate header must expose the same frozen as-of
   boundary, while individual observations retain their own dates.

## 5. Ordered work packages

The file lists below are change boundaries, not permission to edit every file.
Implementers must inspect the current tree and touch the minimum set. Each
package receives a focused commit and updates its tests and verification record.

### WP0 — Freeze baseline and acceptance scenarios

**Depends on:** none  
**Suggested agent:** Luna; Root reviews the inventory and resolves scope gaps.

**Status:** Complete; preservation and browser characterization recorded on
2026-09-07 against baseline revision `898e821`.

**File scope:** existing `apps/mobile/src/*.test.ts`, screen modules,
`phase-8-ui-acceptance-matrix.md`, and `phase-8-verification-record.md`. Add
small test fixtures or test helpers only where a current behaviour is otherwise
unobservable.

**Work:** map every preservation item to its implementation and automated or
manual proof; record representative phone/desktop screenshots of the current
baseline without treating them as design approval; identify missing states
before visual edits begin.

**Tests:** current mobile state tests, TypeScript, Web export, and focused
backend stock/Debate contract tests.

**Definition of done:** the preservation matrix has no unmapped behaviour, the
baseline gates are green, and every later package has an explicit regression
target.

### WP1 — Normalize market-data and indicator integrity

**Depends on:** WP0  
**Suggested agent:** Sol because the work crosses ingestion, storage, API,
client-derived summaries, and CI failure semantics.

**Status:** Implemented locally on 2026-09-07; automated verification is
recorded in [`phase-8-verification-record.md`](phase-8-verification-record.md).
The canonical calculation and sufficiency rules are fixed in
[`phase-8-indicator-contract.md`](phase-8-indicator-contract.md). A live AAPL
refresh remains a deployment operation and is not claimed by this code-only
package.

**File scope:** `backend/app/services/indicators.py`, `market_data.py`,
`ingestion.py`, `supabase_store.py`, stock response schemas/API assembly,
`apps/mobile/src/research/chartMath.ts`, `chartMath.test.ts`, stock-summary
helpers/tests, `scripts/ingest_live_prices.py`, and
`.github/workflows/refresh-aapl-price.yml`.

**Work:** specify and align formulas; validate ordered unique completed closes;
enforce the 50-record verified-history contract for a complete technical view;
return explicit provenance/sufficiency; make refresh errors nonzero; repair and
test stale refresh behaviour.

**Tests:** indicator golden vectors shared or mirrored across backend/client,
minimum-history boundary cases, duplicate/out-of-order records, stale/fresh
responses, ingestion failure exit status, and existing API/cache tests.

**Definition of done:** the same input produces matching displayed indicators,
false-complete history is rejected, CI cannot report a failed refresh as green,
and fresh/stale/unavailable states are deterministic and explained.

### WP2 — Add isolated `review_fixture` mode

**Depends on:** WP1's contract; may begin fixture authoring after WP0  
**Suggested agent:** Terra for coordinated backend configuration, fixtures, API
typing, and client provenance presentation.

**File scope:** `backend/app/config.py`, `backend/app/services/demo_store.py` or
a dedicated review-fixture provider, bounded fixture data under `data/demo/` or
`data/review/`, relevant schemas/API tests, `apps/mobile/src/api.ts`,
`types.ts`, and shared provenance/status components.

**Work:** create deterministic fresh, stale, insufficient, unavailable,
`catalog_only`, full V2, and V2 failure/retry/cancel/reconnect scenarios. Keep
review fixtures separate from live fallback behaviour and prevent production
selection by accidental absence of credentials.

**Tests:** configuration allow/deny matrix, fixture determinism, no outbound
provider calls, visible simulated label in every relevant response/screen, and
production-unavailable tests proving that no fixture values leak into live mode.

**Definition of done:** one documented local setting exposes every visual state
with stable data; screenshots cannot be mistaken for live market output; live
failure never silently switches to simulated facts.

**Status:** Implemented locally on 2026-09-07. `APP_DATA_MODE=review_fixture`
overrides `.env` persistence/provider/auth/Queue/Redis selections, uses only
deterministic in-memory stores, and is rejected outside development, local, or
test environments. AAPL, GOOG, NVDA, TSLA, and MSFT cover fresh, stale,
insufficient, unavailable, and catalog-only states; seven dated macro series
and the deterministic V2 flow are included. The implementation and automated
no-outbound checks are complete, but visual responsive/device review and final
product-owner approval remain WP4/WP8 gates.

### WP3 — Build the prototype-derived design foundation

**Depends on:** WP0; can run alongside WP1/WP2 after preservation is frozen  
**Suggested agent:** Terra; Luna may handle mechanical replacement only after
Terra establishes the token/component contract.

**Status:** Implemented locally on 2026-09-07; automated and browser
characterization evidence is recorded in
[`phase-8-verification-record.md`](phase-8-verification-record.md). This
package establishes the shared deep-theme foundation only. Product-owner visual
approval, Stock workspace information architecture, V2 chat composition, and
complete native/device proof remain open in WP4, WP6, and WP8/WP9.

**File scope:** `prototype.html` as read-only reference,
`apps/mobile/src/theme/tokens.ts`, `theme.ts`, shared components,
`appShell.ts`, `App.tsx`, status bar/navigation, and Web/native typography or
motion helpers.

**Work:** define semantic deep-theme tokens; migrate background/surface/border,
type, spacing, radius, focus, elevation, icons, floating navigation, breakpoints,
and reduced-motion behaviour. Remove screen-local colour duplication without
discarding semantic states.

**Tests:** token/semantic-state tests, App Shell tests, accessibility tests,
TypeScript, Web export, and screenshots at 320/390/768/1280px.

**Definition of done:** all new surfaces consume one theme contract, no core
screen retains the warm-paper shell, contrast and focus meet the acceptance
matrix, and desktop is responsive rather than a fixed 390px frame.

### WP4 — Redesign the AAPL research reference surface

**Depends on:** WP1, WP2, WP3  
**Suggested agent:** Terra for chart/UI implementation; Sol reviews provenance,
formula, and state-boundary correctness.

**Status:** Implemented locally on 2026-09-07. The screen now has a pure
320/390/768/1280 responsive layout contract, measured SVG chart widths,
per-series technical availability states, a phone-first reading order, and a
desktop primary-research/readiness-sidebar composition. Provenance now fails
closed when historical sufficiency fields are absent, and `demo_fallback` is
not eligible for a daily curve. Automated evidence is recorded in
[`phase-8-verification-record.md`](phase-8-verification-record.md). Root-owned
review-fixture browser verification now covers the required Web viewports and
state matrix. Native-device and product-owner visual approval remain open
acceptance gates; this status does not claim subjective design approval.

**File scope:** `apps/mobile/src/screens/StockDetailScreen.tsx`,
`apps/mobile/src/research/chartMath.ts`, stock detail/summary helpers and tests,
finance/chart components introduced under `components/finance/`, and only the
API/schema code needed for sufficiency/provenance fields.

**Work:** implement the deep research workspace, range switching, price and MA
overlays, RSI, MACD, volume, volatility, textual summaries, hover/touch/keyboard
inspection, dates/tooltips, and explicit fresh/stale/simulated/insufficient/
unavailable states. Keep catalog-only behaviour intact.

**Tests:** range and indicator math, per-series sufficiency, keyboard control,
text equivalents, no-overflow layouts, provenance labels, loading/error/empty,
and screenshots at 390px and 1280px using `review_fixture`.

**Definition of done:** local AAPL review shows every technical visual and
interaction with an unavoidable simulated label; insufficient live history
degrades truthfully; the product owner approves the phone and desktop reference
surface before remaining screen migration.

### WP5 — Complete the Debate fact/evidence presentation contract

**Depends on:** WP0 and WP2; finish before WP6  
**Suggested agent:** Sol because this is a high-risk API/domain/UI boundary and
must not invent evidence details on the client.

**Status:** Implemented locally on 2026-09-07. Canonical detail/message APIs
and completed SSE events now carry an additive, server-authored presentation
projection built from the immutable analysis snapshot and persisted citation
allowlist. It includes argument, cited fact excerpts, interpretation,
uncertainty, evidence type/title/source/date/freshness, optional
`support_span`, explicit missing fields, and a public-HTTPS-only source
destination. Legacy records/events remain readable and the client never
reconstructs missing evidence metadata. The chat disclosure UI remains WP6.

**File scope:** Debate schemas/domain/provider/orchestrator/repository/API
assembly as required; `apps/mobile/src/types.ts`, `api.ts`,
`liveDebateView.ts`, `evidencePresentation.ts`, and their tests.

**Work:** ensure a completed turn can render argument, facts used,
interpretation, uncertainty, evidence ID/type/source/date/freshness,
`support_span`, and safe source destination. Preserve immutable evidence and
citation allowlists; represent missing optional detail explicitly.

**Tests:** schema compatibility, invented-ID rejection, support-span/source
mapping, missing/partial evidence, freshness, durable-message reconstruction,
and no frontend inference of unavailable source metadata.

**Definition of done:** the client can render understandable evidence details
from authoritative data for every canonical message without changing Debate
state or fabricating labels.

### WP6 — Implement the V2 chronological chat experience

**Depends on:** WP2, WP3, WP5  
**Suggested agent:** Terra for responsive interaction implementation; Sol
reviews event ordering, persistence, cancellation, and reconnect semantics.

**Status:** Implemented locally on 2026-09-07. The V2 screen is now one
chronological conversation with Bull-left, Bear-right, centred User Challenge,
and centred Interim/Final Judge presentation. Completed messages expose only
the authoritative WP5 fact projection; drafts remain visibly temporary.
Conditional auto-follow is frame-coalesced and preserves the reader's position,
with a centred new-message affordance when they are away from the end. The
isolated fixture now supplies exact selectable terms so the read-only
Explanation interaction is reviewable. Root browser verification covers the
complete two-round flow and 320/390/768/1280 Web layouts. Queue/retry/cancel/
reconnect/failure remain covered by the preserved reducer and state tests;
native-device and product-owner acceptance remain WP8/WP9 gates.

**File scope:** `apps/mobile/src/screens/LiveDebateScreen.tsx`, Debate components,
`liveDebateView.ts`, `debateActionState.ts`, `debateStream.ts`, explanation
views, evidence disclosure components, and focused tests. Backend changes are
limited to defects exposed by WP5/WP6 contracts.

**Work:** render Bull-left/Bear-right chronological bubbles, round/exchange
markers, temporary stream state, centred Interim/Final Judge, centred User
Challenge, expandable facts/evidence, Explanation, conditional autoscroll,
new-message affordance, queue/retry/cancel/reconnect/failure, and History reopen.
Label V2 as primary and Legacy as fallback without enabling production flags.

**Tests:** reducer/event order, draft-to-canonical transition, Challenge gating,
Explanation immutability, retry/cancel/reconnect, accessible disclosure state,
focus/autoscroll policy, transcript ordering, and 320/390/768/1280px screenshots.

**Definition of done:** the full two-round fixture reads as one conversation;
all roles and interventions are unambiguous without relying on colour; Final
Judge ends the transcript; every prior V2 operational state remains reachable.

### WP7 — Migrate all remaining surfaces

**Depends on:** WP3 and approval of the WP4/WP6 reference direction  
**Suggested agent:** Terra for complex screens; Luna for isolated token adoption,
snapshot/state-test updates, and other mechanical conversions.

**Status:** Implemented locally on 2026-09-07. Terra migrated Auth/Watchlist
and Evidence/Examination; Luna migrated History/About/Legacy and shared Legacy
cards; Root integrated the shared reading/status foundation and performed Web
browser verification. A Sol final audit found and Root closed public-link,
Auth-field feedback, and Legacy/V2 copy gaps. The full backend/mobile gates
pass. Native, 200% zoom, reduced-motion, recovery-state, and product-owner
acceptance remain WP8/WP9 rather than being inferred from this status.

**File scope:** `AuthScreen.tsx`; Watchlist, Evidence, Examination, History,
Legacy Debate, and About screen modules; shared common/debate/feedback
components; `App.tsx`; their focused tests.

**Work:** apply the approved theme and interaction grammar while retaining every
item in the preservation contract. Consolidate duplicated screen-local styles
and keep diagnostics secondary to user-facing guidance.

**Tests:** all mobile state tests, targeted accessibility checks, TypeScript,
Web export, and required normal/empty/loading/error screenshots.

**Definition of done:** all core routes look and behave as one product; no warm
or standalone V2 mini-theme remains; catalog, legacy, error, and diagnostic
states have not disappeared.

### WP8 — Integrated regression, accessibility, and device proof

**Depends on:** WP1–WP7  
**Suggested agent:** Luna executes deterministic matrices and records results;
Root reproduces failures and makes final acceptance judgments. Terra or Sol
owns fixes according to the failing layer.

**File scope:** tests, non-secret test helpers, acceptance matrix, and
`phase-8-verification-record.md`. Production configuration is read-only here.

**Work:** run full backend/mobile gates; review 320/390/768/1280px, keyboard,
screen reader labels/status, 200% zoom, reduced motion, iOS simulator, Android
simulator, and one physical device. Exercise every fixture and recovery state.

The recovery set must include an active-Debate admission conflict. The backend
one-active-Debate rule is expected and valid: when the test user already has an
unfinished Debate in `awaiting_user`, a second `POST /debates` returns `409
Conflict`. The original frontend exposed that error only in the stock page's
top-level feedback area, while the Debate action was at the bottom of the page;
the action area therefore appeared unresponsive and offered no way to open the
existing Debate or go to History. This was an open frontend recovery-interaction
issue, not a V2 state-proxy issue.

The `awaiting_user` interaction set must also distinguish a question from a
Round 2 intervention. Selecting a completed point opens an educational,
read-only modal in the current viewport; it must not queue Round 2. The modal
must support Close, Cancel, backdrop dismissal, Android Back, keyboard use, and
an explicit second step before the Challenge endpoint is called. Product-owner
page inspection follows a concise checklist; engineering reproduces reported
failures, changes code, and retains the automated evidence.

Commit `0e7c813` implements the recovery interaction locally: API status is
preserved, synchronous duplicate submissions are protected, a recovery card is
shown near the Debate action, and the user can open the current Debate or go to
History. The implementation is awaiting product-owner visual confirmation;
this does not claim Xcode, physical-device, or final visual acceptance.

**Tests:** complete backend suite; `npm run test:stream`; `npm run typecheck`;
`npm run build:web`; focused proxy/API coverage for the active-Debate conflict
and recovery entry point; recorded manual accessibility/device matrix. The
latest local gate has 370 passing backend and 80 passing mobile tests, with
typecheck and Web export also passing. Commit `8c9278c` adds the V2 transient
proxy coverage for reconnect, retry, cancel, and failure (15 passing tests).

**Definition of done:** no preservation regression, no unreviewed required
state, all automated gates pass, and limitations are recorded rather than
silently waived.

### WP8L — Controlled local Live Data and Live AI acceptance

**Depends on:** WP1, WP4, WP5, WP6, and the WP8 automated baseline
**Status:** In progress; implementation authorized on 2026-09-08 after plan
review. Each independently verified code slice includes documentation and its
own commit. Local implementation is not evidence of live/device acceptance.
The initial engineering slices use offline tests; quota-bearing refreshes and
model acceptance follow the data gates below.
**Owner:** Root controls quota-bearing calls and final acceptance; Sol owns
data/provenance, Queue, provider, and interruption contracts; Terra owns the
client reveal scheduler after those contracts are fixed; Luna may execute only
credential-free matrices and evidence collection.

**Current readiness:** a safe presence-only local configuration audit confirms
that Supabase, Groq, Alpha Vantage, Finnhub, and SEC settings are available in
the ignored `.env`. The V2 workflow, Queue, Debate streaming provider, and Expo
V2 flags are unset and therefore retain safe false/deterministic defaults. The
current `review_fixture` server cannot be used as Live Acceptance evidence.

Implementation review: the dependency order is accepted. The reveal scheduler
can be developed against synthetic ordered events alongside the data contract;
live execution still waits for preflight. Review must include exchange-local
close timing, quote-aware snapshot cache identity, and completion/Stop races.
Sol owns the backend contract, Terra the mobile scheduler, Luna independent
verification discovery, and root integration, regression checks, and commits.

#### WP8L.1 — Freeze the meaning of “current”

2026-09-09: quote/completed-close backend slice implemented. Immutable context
includes capture time, latest completed-close date, and a separate Finnhub quote
factor with original retrieval time retained across cache hits. Live Turn
admission rejects invalid/insufficient/stale daily history and unavailable,
stale, future, or inconsistent quotes. NY 16:15/weekend cutoff is conservative;
an authoritative holiday/early-close calendar and evidence/filing/macro admission
gates remain pending. This does not close WP8L.1 or live/device acceptance.


- Treat `GET /stocks/AAPL/quote` as the latest provider quote. Preserve its
  source timestamp, retrieval time, age, session/market context when available,
  and unavailable/stale state. Do not promise exchange-grade real-time service
  beyond the provider contract.
- Treat the newest validated Alpha Vantage daily row as the latest completed
  close for charts and indicators. Require chronological unique positive OHLCV,
  at least 50 valid closes for the complete technical view, and an advancing
  refresh result.
- Do not splice the latest quote into historical closes. Display both values
  when available, with labels such as `Latest provider quote` and
  `Latest completed close`.
- Define a `MarketQuoteFactor` or equivalent immutable observation so a Debate
  can use the latest accepted quote without changing technical-indicator math.
  Record the snapshot capture time and retain the observation date/source of
  every close, quote, filing fact, evidence item, and macro series.
- Fail closed: if required AAPL history or snapshot provenance is stale,
  inconsistent, or unavailable, allow research viewing with a warning but do
  not start a Live AI Debate that implies current inputs.

#### WP8L.2 — Refresh and preflight real AAPL inputs

Run external writes only after explicit quota/write authorization and never
print secrets. Execute one bounded source at a time:

1. refresh AAPL daily closes once with `scripts/ingest_live_prices.py`;
2. refresh recent Apple/SEC evidence and structured filing facts with
   `scripts/ingest_live_evidence.py`;
3. refresh the seven macro series with `scripts/ingest_macro_context.py`;
4. refresh weekly AAPL history only if the weekly cache is due; and
5. read back `/stocks/AAPL/quote`, `/stocks/AAPL/bundle`, indicators, evidence,
   and coverage before spending model quota.

Record, without secret values: source, newest observation/publication time,
retrieval time, stale flag, row count, sufficiency, and data mode. Stop the lane
if the daily cache does not advance when it should, if fewer than 50 valid
closes remain, if `review_fixture`/`demo_fallback` appears, or if page and
snapshot values disagree.

#### WP8L.3 — Prove the provider and Queue boundary before opening Expo

- Revalidate the configured Groq model through the provider's current model
  listing and rate-limit documentation; do not assume a historical model ID or
  quota remains valid.
- Run the existing quota-confirmed Groq streaming verifier once. Require six
  ordered Bull/Bear Turn streams, nonzero token accounting, valid citations,
  canonical reload, and safe cleanup. Do not print generated text or prompts.
- Document the present limitation: `DEBATE_STREAMING_PROVIDER=groq` applies to
  Bull/Bear Turns, while Interim/Final Judge still use the deterministic Judge
  provider and do not emit `judge.delta`. This may be used as an explicitly
  labelled intermediate smoke test, but it is not a fully Live AI Debate.
- Add a bounded asynchronous Judge provider and `judge.delta` contract before
  claiming every visible agent is model-generated. Apply the same evidence
  allowlist, output bound, guardrails, token ledger, retry classification,
  completion validation, cancellation, and reconnect rules used for Bull/Bear.
- Keep Explanation as a separately metered provider choice. A Live Debate test
  must not silently enable paid/live Explanation calls.

#### WP8L.4 — Separate network streaming from human-visible pacing

- Maintain two ordered states per active message: provider-received content and
  user-revealed content. Append SSE deltas to a bounded buffer; reveal English
  by word and CJK text by Unicode grapheme using a configurable cadence.
- Receiving `turn.completed` or `judge.completed` stores the canonical record
  but must not replace a partially revealed bubble with the full message. The
  final card becomes canonical only after the reveal buffer drains or the user
  explicitly chooses `Show full response`.
- Only one agent bubble streams at a time. The next role cannot become visibly
  active before the prior message is canonical and its reveal policy is
  settled.
- Bound memory and latency when Groq produces faster than the display cadence.
  Preserve order, whitespace, punctuation, and grapheme integrity; never drop
  text during normal playback.
- Reduced-motion, screen-reader, app-background, reconnect, and saved-History
  paths must not replay decorative typing. Screen readers announce logical
  chunks or the completed message, not every character. Historical completed
  messages load immediately.

#### WP8L.5 — Implement immediate interruption and interjection

- `Stop here` freezes the displayed prefix and clears undisplayed buffered text
  immediately on the client, before network acknowledgement.
- The backend atomically invalidates the expected generation against Turn
  completion/next-Turn admission. No subsequent Bull, Bear, or Judge provider
  request may start; late events are ignored.
- Persist only a server-validated prefix as an explicitly incomplete,
  interrupted record. The existing `DebateMessage` schema permits
  `is_complete=false` with `cancelled_at`; repository/API/event behavior and a
  bounded durable draft checkpoint still need implementation. Do not attach
  unverified citations or present the prefix as a completed claim.
- Show a user composer at that point. A read-only explanation, a user opinion
  that influences later discussion, ending the Debate, and continuing from a
  new generation are four distinct actions.
- If the user continues, create one new generation from the last complete
  canonical prefix plus the explicitly recorded interjection. Never revive the
  cancelled generation, reveal previously buffered text, or duplicate Messages,
  citations, Queue jobs, or token entries.

#### WP8L.6 — Run the Expo Go acceptance session

Use a dedicated non-production Supabase test user and the standard data mode.
For the first controlled pass, keep API, in-process Worker, and SSE broker in
one FastAPI process and one instance. This is required because transient events
are currently process-local. Start without `--reload` so a code watcher cannot
interrupt a quota-bearing Session. Mount Expo with Supabase auth and the V2
flag, using loopback for the iOS Simulator or the workstation LAN address for a
physical device.

The recorded pass must prove:

- the app contains no simulated-data banner or fixture IDs;
- quote, completed close, chart, indicators, evidence, and Debate snapshot all
  show their source and date without contradicting one another;
- `POST /debates` returns `202` before generation completes and the Queue state
  appears before the first model text;
- Bull, Bear, and—after its provider slice—Judge reveal incrementally in order,
  with one active bubble and no full-result jump;
- rebuttals target the immediately prior opponent and citations stay within the
  frozen evidence allowlist;
- Stop freezes the exact visible prefix immediately, prevents later agents,
  survives reload, and accepts a user interjection without an implicit restart;
- SSE reconnect, app background/foreground, one provider retry, terminal error,
  cancellation, and History reopening remain understandable; and
- provider request counts and token totals stay inside the declared per-session
  budget. At most one live Session runs concurrently during acceptance.

#### WP8L.7 — Topology and release boundary

The existing single-process Worker in the FastAPI lifespan is the accepted
local/staging topology for this lane. Do not deploy a separate Render background
Worker while SSE deltas remain process-local: canonical completion might persist
but the API process would not receive the live delta stream. Before splitting
processes or scaling the API, add a durable/shared event stream or draft
checkpoint and repeat reconnect/interruption tests.

Render free Web services may cold-start and restart. Pre-warm `/health`, record
cold-start behavior, keep the SSE connection active during the bounded test,
and rely on Supabase rather than local disk for canonical state. Hosted flags
remain off until WP10 deploys one immutable SHA with a rollback that can disable
V2/Queue/live provider independently.

**Definition of done:** one recorded Expo Go session uses verified standard-mode
AAPL inputs and real streamed model Turns; the UI visibly paces deltas; immediate
interruption and user interjection meet the contract; every deterministic/live
role is labelled honestly; the Session reloads from durable state; cost,
freshness, citation, and topology evidence is recorded; no public or production
flag is changed.

### WP9 — Product-owner visual and interaction acceptance

**Depends on:** WP4, WP6, WP7, WP8, and WP8L
**Owner:** Root prepares evidence; product owner decides acceptance. No agent may
self-approve subjective design quality.

**Review set:** fixture-backed AAPL workspace and complete V2 Debate at 390px
and 1280px; the controlled WP8L Expo Go session with standard AAPL data and
Live AI pacing/interruption; plus representative Authentication, Discovery,
Watchlist, Evidence, History, stale, unavailable, and error states.

For efficient review, the product owner may run a short visual/page checklist
and report observations rather than reproduce the full engineering matrix:

- Can the primary action, current state, error, and recovery action be found at
  the point of interaction without scrolling to another page region?
- When an active Debate already exists, is the `409` explanation clear and is
  there an obvious action to open that Debate or go to History?
- At 390px and 1280px, are hierarchy, density, charts, evidence, and Debate
  pacing understandable without clipped content or horizontal overflow?
- Do loading, empty, stale, unavailable, retry, cancel, and reduced-motion
  states communicate what happened and what the user can do next?

The product owner reports observations, screenshots, and requested severity to
engineering. Engineering owns the reproducible entry point, code changes,
focused automated checks, and recorded acceptance evidence; a product-owner
review is not evidence that an unimplemented fix is complete.

**Decision:** record approved elements, requested revisions, severity, and the
commit SHA reviewed. Revisions return to the owning work package and repeat its
tests.

**Definition of done:** explicit product-owner approval is recorded for visual
style, information density, charts, micro-interactions, evidence comprehension,
Debate pacing, Judge hierarchy, and responsive behaviour.

### WP10 — Same-SHA staging release gate

**Depends on:** WP8L and WP9
**Suggested agent:** Sol prepares and verifies the cross-layer release; Root
authorizes any external deployment and public-demo change.

**File scope:** deployment configuration, safe environment documentation,
staging smoke scripts/tests, and verification records. Phase 9 Replay,
observability, resilience, and final portfolio proof remain out of scope.

**Work:** deploy the frontend and backend from the exact same commit SHA; verify
the stock bundle/API contract, data provenance, chart states, V2 feature flags,
auth/CORS, cold start, rollback target, and a bounded end-to-end path. Never
publish a frontend that expects an API route absent from its paired backend.

**Tests:** health and version/SHA match, authenticated stock and Debate smoke,
fresh/stale/unavailable behaviour, responsive browser smoke, no fixture leakage
into production, and rollback rehearsal or documented reversible target.

**Definition of done:** staging reports one matching SHA, all smoke gates pass,
the product owner reviews staging, and changing the public demo remains a
separate explicit authorization.

## 6. Agent allocation and review policy

Use the lowest-cost model that is sufficient for the risk, not the lowest model
regardless of risk.

| Model | Suitable work | Do not assign alone |
| --- | --- | --- |
| Luna | Inventory, deterministic test execution, screenshot/state matrices, mechanical token adoption, documentation evidence | Product architecture, provenance semantics, cross-layer contracts, final integration decisions |
| Terra | Theme/components, responsive screens, chart interactions, fixtures with an established contract, focused UI refactors | Unreviewed changes to financial formulas, evidence trust boundaries, deployment compatibility |
| Sol | Indicator/provenance contracts, Debate evidence/API changes, workflow failure semantics, cross-layer integration, staging compatibility | Large mechanical sweeps that Luna or Terra can complete from a fixed contract |

The Root agent owns dependency order, conflict resolution, scope control, review,
integration, final test execution, and all completion checkboxes. Sub-agents
must receive bounded file scopes and cannot mark a package or Phase 8 complete.
Root re-reads diffs, reruns proportionate tests, checks preservation, and rejects
outputs that merely look correct in one screenshot.

Recommended execution waves:

1. Luna runs WP0 while Root validates scope.
2. Sol runs WP1; Terra may draft WP2 fixtures against the documented contract.
3. Terra runs WP3 after WP0, then WP4 after WP1/WP2; product owner reviews the
   first reference surface.
4. Sol runs WP5; Terra then runs WP6; Root validates the full state machine and
   product owner reviews the second reference surface.
5. Terra and Luna divide WP7 by complexity with non-overlapping files.
6. Luna executes WP8; Root reproduces and adjudicates results.
7. Root coordinates WP8L in bounded slices: Sol fixes live data/provider and
   interruption contracts, Terra implements reveal pacing, and Root performs
   the quota-bearing Expo Go acceptance.
8. Root conducts WP9; Sol supports WP10 only after approval.

## 7. Local terminal acceptance target

The implemented configuration names and commands must be documented in setup
guidance during WP2. The target developer experience is equivalent to:

```sh
cd backend
ENVIRONMENT=development APP_DATA_MODE=review_fixture uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```sh
cd apps/mobile
EXPO_PUBLIC_AUTH_MODE=demo EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

The actual accepted environment-variable name may change during implementation
if configuration conventions require it, but one explicit command pair must:

- start without market-data or model credentials;
- show the global prototype-derived deep style;
- show all price and technical charts with stable interaction;
- show the permanent simulated-data label;
- run the complete V2 Round 1, Interim Judge, Challenge, Round 2, and Final Judge
  review flow; and
- make loading, stale, insufficient, unavailable, retry, cancel, reconnect, and
  error states directly reviewable.

WP8L adds a separate credentialed command pair; it must never replace the safe
fixture default or be copied into CI. After real-data preflight and explicit
quota authorization, the intended local shape is:

```sh
cd backend
ENVIRONMENT=development APP_DATA_MODE=standard \
DEBATE_WORKFLOW_V2=true DEBATE_QUEUE_ENABLED=true \
DEBATE_STREAMING_PROVIDER=groq \
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal for the iOS Simulator:

```sh
cd apps/mobile
EXPO_PUBLIC_AUTH_MODE=supabase \
EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 \
npx expo start --localhost --clear
```

The credential values remain only in the ignored root `.env`; command output,
screenshots, verification records, and Git history must not contain them. A
physical device uses the workstation LAN address and requires a separate
reachability check.

## 8. Phase closure and boundary with Phase 9

Phase 8 closes only after WP0–WP10, including WP8L, meet their definitions of
done and the parent plan checklist is updated with recorded evidence. In
particular:

- automated tests do not substitute for product-owner visual approval;
- screenshots do not substitute for keyboard, accessibility, or device proof;
- `review_fixture` does not substitute for production data-integrity tests;
- a provider key or enabled flag does not substitute for recorded Live AAPL,
  streaming, pacing, interruption, token, and persistence evidence;
- staging does not pass unless frontend and backend use the same SHA; and
- the public demo is not changed without explicit authorization after staging.

Phase 9 remains Planned. Its sanitized Demo Replay, observability, resilience,
load evidence, final release proof, classroom script, and portfolio claims begin
only after this remediation phase is accepted. Phase 8 fixtures exist to expose
UI states deterministically; they must not be presented as the Phase 9 Replay
deliverable.

### WP8L engineering checkpoint — 2026-09-09 offline capture audit

Added the credential-free `scripts/verify_live_snapshot.py` diagnostic for
Session/bundle exports. It fails on inconsistent market inputs, page indicators,
missing/different quote retrieval times, invalid evidence dates, insufficient
or duplicate macro series, and failed factor providers. This is a bounded WP8L.2
prerequisite only: it does not close live refresh or API evidence/macro admission.
Next slice: implement server-side evidence/filing/macro eligibility with
source-specific freshness rules before running model acceptance.

### WP8L engineering checkpoint — 2026-09-09 live evidence admission

Live Turn admission now selects news and filing documents before quote lookup
and Session/Job creation. It recalculates the existing 7-day news and 120-day
filing policy at capture time; future/malformed dates, other tickers, missing
Supabase document provenance, and invalid source URLs are excluded. At least
one eligible document of each category is required, otherwise admission returns
409. Conflicting duplicate IDs also fail; exact duplicates are deduplicated.
Only selected IDs enter the immutable citation allowlist. Technical context is
provided by validated price factors, not inherited demo technical evidence.

This is filing-document eligibility, not structured financial-fact completeness
or SEC-origin authentication. Macro per-series freshness/admission and structured
financial-fact selection remain the next slices. Deterministic/review research
paths retain their existing behavior; no external refresh or live call was run.

### WP8L engineering checkpoint — 2026-09-09 macro admission

Live Turn admission now requires all seven named macro series from the existing
configuration and validates source/unit/provider ID, finite values, unique
codes, observation/retrieval chronology and age. Missing/invalid macro context
returns 409 rather than silently admitting partial context. The initial policy
uses 7-day age limits for these daily series; provider publication/vintage
verification remains part of live preflight. Next bounded slice: structured
financial-fact selection/provenance. This does not close Live Acceptance.

### WP8L.4 implementation checkpoint — 2026-09-09

Reveal scheduler is implemented and offline-verified (91 mobile tests,
typecheck, Web export). Provider-received text and visible prefix are separate;
completion waits for reveal, next visible agent waits for prior display,
and Unicode segmentation uses a pinned Hermes-compatible implementation.
Native/device and screen-reader behavior still require acceptance. WP8L.5 Stop
must consume this visible prefix; the existing terminal Cancel is unchanged.

### WP8L.3 implementation checkpoint — 2026-09-09

Asynchronous Judge provider, factory, collector, SSE, cancellation boundary and
per-message model/token metadata are implemented and verified with 424 backend
tests plus one successful bounded synthetic Groq probe. Selection is separately
default-off. This supersedes the earlier non-streaming Judge limitation for
queued V2 only. Current-data, durable immediate interruption and device gates
remain open; server-authored structural labels are not model-extracted findings.


### 2026-09-09 — WP8L interruption foundation

Implemented default-off `DEBATE_INTERRUPTIONS_ENABLED`: checkpoint generated text before publishing each delta and accept an owner/generation-scoped `/debates/{id}/interrupt` request. The repository atomically rotates the generation, preserves the exact visible prefix as incomplete (including trailing whitespace), removes later messages and cancels queued jobs. Running workers acknowledge cancellation and retain observed request usage. Completed output can also be shortened when display is still catching up. Repeated identical requests are idempotent; invented prefixes and stale generations are rejected.

Validation: backend suite 434 passed (one existing Starlette/httpx deprecation warning); regression coverage includes API flag/ownership, exact prefix, late provider output, canonical completion before interruption, and repeat requests. No market or model calls in this step.

Limitations: SQL migration `20260909_debate_draft_interruption.sql` is authored but NOT applied or PostgreSQL-runtime validated. Checkpointing currently performs one synchronous persistence write per delta and needs hosted latency measurement. Client Stop here, user interjection and explicit continuation remain pending; this is not WP8L.5 acceptance. Feature stays disabled until migration and end-to-end checks pass.


### 2026-09-09 — WP8L client Stop here integration

Added default-off `EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED`. While a message is revealing, Stop here freezes the last rendered prefix immediately, stops the local stream and submits that exact prefix to `/interrupt`. Failure keeps the display frozen and permits an identical retry; only a matching incomplete canonical response releases the local freeze. Reconnect, accessibility settlement, Show full and late provider completion cannot expand frozen text. Incomplete records explicitly say “Stopped here · Incomplete response” and render raw retained content without old full-text presentation sections.

Validation: mobile TypeScript check passed; 93 Node tests passed, including rendered-vs-received prefix and stale presentation regression; Expo Web export with the interruption flag enabled passed. This is build/unit verification, not browser or Expo Go device acceptance. No market/model calls or persisted environment changes.

Remaining: hosted migration/runtime verification, persistence latency, interruption before the first draft arrives, recovery of an unconfirmed stop after app termination, and user interjection/explicit continuation. The flag remains false in `.env.example`; do not claim the entire Stop here contract is complete.
