# Phase 8 Design Remediation Execution Plan

**Status:** In progress  
**Last updated:** 2026-09-07
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

**Tests:** complete backend suite; `npm run test:stream`; `npm run typecheck`;
`npm run build:web`; recorded manual accessibility/device matrix.

**Definition of done:** no preservation regression, no unreviewed required
state, all automated gates pass, and limitations are recorded rather than
silently waived.

### WP9 — Product-owner visual and interaction acceptance

**Depends on:** WP4, WP6, WP7, WP8  
**Owner:** Root prepares evidence; product owner decides acceptance. No agent may
self-approve subjective design quality.

**Review set:** AAPL workspace and complete V2 Debate at 390px and 1280px,
plus representative Authentication, Discovery, Watchlist, Evidence, History,
stale, unavailable, and error states.

**Decision:** record approved elements, requested revisions, severity, and the
commit SHA reviewed. Revisions return to the owning work package and repeat its
tests.

**Definition of done:** explicit product-owner approval is recorded for visual
style, information density, charts, micro-interactions, evidence comprehension,
Debate pacing, Judge hierarchy, and responsive behaviour.

### WP10 — Same-SHA staging release gate

**Depends on:** WP9  
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
7. Root conducts WP9; Sol supports WP10 only after approval.

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

## 8. Phase closure and boundary with Phase 9

Phase 8 closes only after WP0–WP10 meet their definitions of done and the parent
plan checklist is updated with recorded evidence. In particular:

- automated tests do not substitute for product-owner visual approval;
- screenshots do not substitute for keyboard, accessibility, or device proof;
- `review_fixture` does not substitute for production data-integrity tests;
- staging does not pass unless frontend and backend use the same SHA; and
- the public demo is not changed without explicit authorization after staging.

Phase 9 remains Planned. Its sanitized Demo Replay, observability, resilience,
load evidence, final release proof, classroom script, and portfolio claims begin
only after this remediation phase is accepted. Phase 8 fixtures exist to expose
UI states deterministically; they must not be presented as the Phase 9 Replay
deliverable.
