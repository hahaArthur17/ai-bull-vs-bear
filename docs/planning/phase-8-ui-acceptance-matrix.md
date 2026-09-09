# Phase 8 UI acceptance matrix

**Status:** Active for Phase 8  
**Owner:** Mobile application  
**Last updated:** 2026-09-08

This matrix is the visual and interaction acceptance contract for the
financial-research UI redesign. It supplements executable checks; it does not
replace the existing API contracts, provenance rules, or Phase 7 interaction
boundaries.

## Product direction

The repository-root [`prototype.html`](../../prototype.html) is the formal
visual reference for Phase 8. The interface should feel like a dark,
information-dense research workspace: clear market hierarchy, purposeful
bullish/bearish signals, and readable evidence before visual decoration. The
prior warm-paper visual direction is not an acceptable alternative. Colour must
never be the sole carrier of financial direction, freshness, job state, or
validation feedback. The same semantic components and content hierarchy must
work on native mobile and Expo Web.

### Design-system acceptance

The implementation must turn the Prototype language into shared semantic
tokens and reusable components, rather than retaining a warm global theme plus
a separate hard-coded dark Debate theme.

| Token family | Required visual direction | Acceptance boundary |
| --- | --- | --- |
| Canvas and surfaces | Deep navy canvas (`#09101d`), darker outer canvas (`#050a12`), and layered blue-navy surfaces | No warm paper/background palette remains on a production surface. |
| Text and structure | Near-white primary text and muted blue-grey metadata | Contrast, hierarchy, and focus state remain legible without relying on colour alone. |
| Market roles | Bull = teal/green (`#6cd8c8`); Bear = pink (`#f59ba8`); Evidence and Judge = gold (`#ffc66f`) | Role names/icons/patterns accompany colour; the colours are not repurposed for unrelated states. |
| Interaction language | Short, restrained transitions; floating rounded navigation; elevated cards and clear evidence hierarchy | Prototype interactions may be adapted for real content and accessibility, not copied as static decoration. |

The Prototype is inspiration, not a layout constraint: desktop must not be
forced into a 390 px phone frame, static mock content must be replaced by real
application states, and new functional states introduced after the Prototype
must remain visible and usable.

Every redesign slice must preserve these product invariants:

- `catalog_only` securities remain identity-only and never initiate market-data
  or model calls.
- Source, evidence date, freshness, coverage, and warnings remain visible
  wherever analysis is presented.
- V2 Debate and the Groq Explanation provider stay default-off. Explanation is
  read-only and cannot mutate Debate state. A controlled Live Acceptance run
  may opt into V2/Queue/Groq explicitly without changing the safe default.
- Challenge is available only during the durable `awaiting_user` pause; it is
  not a general transcript branching affordance.
- Diagnostic/provider implementation detail is progressively disclosed and is
  never the primary status copy for a user.

## View and state coverage

| Surface | Required states to review | Acceptance evidence |
| --- | --- | --- |
| Authentication | initial form, invalid input, submit disabled, submitting, authentication failure, sign-up confirmation | Inputs are labelled; errors are announced and tied to the affected field; submit cannot duplicate a request. |
| Discovery and Watchlist | saved list, empty list, search in progress, search results, no results, search failure, `catalog_only`, `debate_ready` | Search and watchlist controls retain clear names; coverage labels have text as well as visual treatment; empty and failure states provide a recovery action. |
| Stock research workspace | bundle loading, bundle failure, latest provider quote, latest completed close, stale/warning evidence, review fixture, watchlist add/remove, `catalog_only` | Quote and completed close have distinct labels/source/timestamps; evidence date, freshness, and all warnings remain readable; an identity-only security has no analysis CTA. |
| Charts and technical signals | fresh verified history, stale history, `review_fixture`, unavailable/no data, partial history, narrow layout, pointer/touch/keyboard interaction where controls exist | Price and every eligible indicator trend render with a textual summary; legends and trends do not depend on colour alone; layout does not horizontally overflow; unavailable data never becomes a plausible fake market chart. |
| Evidence and Examination | evidence list, missing/partial evidence, claim selected, examination loading, result, request failure | Each evidence item retains source, date, freshness, and link/identifier; loading and error copy do not imply a completed answer. |
| Legacy Debate | idle/start, active stream, completed transcript, error | Existing start and transcript behavior remains available until shared presentation is adopted; evidence provenance remains legible. |
| V2 Debate | queued, running, provider deltas, paced reveal, immediate interruption/interjection, retry delay, failed, cancelled, `awaiting_user`, final; connection recovery; point-question modal closed/loading/result/error; Round 2 confirmation | The transcript is a chronological chat timeline: Bull messages align left, Bear messages align right, and interim/final neutral Judge summaries are horizontally centred. On mobile it remains chronological with readable offset bubbles, not narrow two columns. Only canonical messages read as durable; drafts and interrupted prefixes are explicitly temporary/incomplete. A fast provider cannot cause full text to jump into view before the reveal scheduler drains. `Stop here` freezes already revealed text immediately, discards undisplayed text, prevents later agents, and opens a user interjection path without implicit continuation. “Ask about this point” remains a separate read-only educational modal; Round 2 requires a separate explicit confirmation. Close, Cancel, backdrop tap, Android Back, and keyboard access remain usable. |
| History | empty, analysis item, V2 active item, interim Judge, final Judge, load failure | Final and interim Judge states remain distinct; reopening a saved session restores its matching ticker bundle. |
| About and diagnostics | normal content, sign-out available, diagnostic disclosure expanded | Product guidance precedes technical detail; any disclosure has an accessible name and state. |

## Market-data and chart acceptance

`demo_fallback` is an internal resilience/test compatibility state; it must not
be the only way a reviewer can inspect charts, and it must not be presented as
real market data. A dedicated `review_fixture` must provide deterministic
history and full chart interaction for local/UI review. It must be visibly and
persistently labelled, for example: “SIMULATED DATA · LOCAL UI REVIEW · NOT A
MARKET PRICE”.

| Data state | Required display |
| --- | --- |
| latest provider quote | Current provider value with source timestamp, retrieval/freshness state, and no claim that it is a completed daily close. |
| latest completed close | Newest validated daily OHLCV close used by charts/indicators, with trading date and source; never labelled as an intraday quote. |
| `live/fresh` | Full price and eligible technical trends with source, observation time, and freshness. |
| `live/stale` | Historical curves remain inspectable; stale/historical status and date are prominent. |
| `review_fixture` | Full deterministic curves and interactions with the persistent simulated-data label. |
| `unavailable` | No fabricated price/indicator output; clear cause and recovery action. |
| `catalog_only` | Identity details only; no market-data or analysis implication. |

Technical visibility is per series, not an all-or-nothing gate. At minimum:
price requires two observations; RSI requires 15; MA20 requires 20; rolling
volatility requires 21; MA50 requires 50; MACD requires the implemented
calculation window. A series below its threshold shows an explicit insufficient
history state without hiding otherwise eligible price or indicator series.

For every rendered indicator, range changes, hover/focus/touch inspection,
date/value tooltip or textual equivalent, and visible selected point must use
the same underlying value. Frontend and backend calculations for displayed RSI
and volatility must be checked for one shared definition before final closure.

## Live Data and Live AI acceptance

Status at `50d9885` (2026-09-09): data/provider/reveal and default-off Stop
foundations have implementation evidence; this entire matrix is not yet passed.
See [`remaining sequence`](wp8l-next-steps.md).

The controlled live run supplements fixture-based UI review. It is not a public
release and must use a dedicated non-production account, bounded provider quota,
standard data mode, V2 Queue admission, and a genuinely streaming provider.

| Gate | Required evidence |
| --- | --- |
| Data preflight | No simulated banner or fixture IDs; AAPL quote, completed close, chart history, indicator sufficiency, evidence, and macro context expose non-conflicting source/date/freshness. |
| Frozen snapshot | Debate displays its capture time and all Bull/Bear/Judge requests use the same immutable inputs even if a newer quote arrives. |
| Queue admission | `POST /debates` returns `202` before completion; queued/running state is visible before model text. |
| Provider truth | Every completed message exposes provider/model/stream-mode metadata in diagnostics; deterministic Judge or Explanation output is labelled until replaced by its own live contract. |
| Reveal pacing | Only one active bubble reveals at a time; English words and CJK graphemes remain ordered; canonical completion cannot force an early full-text jump; `Show full response` is explicit. |
| Immediate interruption | Visible prefix freezes before network acknowledgement, undisplayed text stays hidden, server-confirmed interruption blocks new old-generation admission, already-dispatched usage is retained, the prefix remains explicitly incomplete after reload, and the user can interject without automatically restarting. |
| Stop boundaries | Queued/before-first-delta, empty prefix, Judge, completion-before-reveal, timeout, duplicate requests and two-client races have explicit outcomes. |
| Interjection and Continue | Opinion submission does not call a model; explicit Continue creates one new generation/job, retains frozen inputs, and never revives hidden output or duplicates usage. |
| Unconfirmed Stop recovery | App termination/reopen restores the pending request or confirmed interruption; no automatic reveal or model restart. |
| Recovery | App background/foreground, SSE reconnect, retry, terminal failure, cancellation, and History reopen preserve durable state without replaying completed text as new typing. |
| Cost boundary | Provider request count, per-turn cap, total token use, retry count, and one-live-session concurrency are recorded without prompts or secrets. |

## Debate facts and citation acceptance

Each completed Bull/Bear message must separate the argument from the facts it
uses and the limits of its interpretation. The collapsed message may surface up
to three immediately useful facts with a value, observation/publication date,
and source, but every cited item must remain reachable in expanded detail.
Citation chips must be actionable: their expanded detail includes evidence ID,
title, type, date, freshness, supporting span/quotation when available, and
original-source link. IDs alone are not sufficient evidence presentation.

The desktop transcript is centred and constrained to a readable chat width;
it must not consume the entire viewport. A collapsible evidence rail may be
provided as secondary detail. Interim Judge follows its round, the user
Challenge is visually distinct from Bear, and Final Judge is the final,
centred conclusion. Streaming must not forcibly scroll a user who is reading
earlier messages; instead surface a new-message affordance.

## Responsive acceptance

Review every affected surface at these CSS viewport widths in Expo Web. Widths
are content constraints, not a device emulation claim.

| Viewport width | Required outcome |
| --- | --- |
| 320 px | Single-column content; no clipped text or horizontal page scroll; primary actions remain reachable. |
| 390 px | Comfortable phone baseline; persistent navigation, cards, charts, and composers fit without overlap. |
| 768 px | Compact tablet layout may introduce columns only when each column remains readable and keyboard order follows visual order. |
| 1280 px | Research workspace uses available space without excessively long reading lines; secondary detail does not displace evidence or primary actions. |

At every width, use fluid containers with explicit minimum widths for data
visualisations. If a visualisation cannot shrink safely, present its textual
summary before an intentional, labelled horizontal scroll region rather than
allowing the page to overflow.

## Accessibility acceptance

- All interactive controls have a programmatic name, role, visible focus
  indicator on Web, and at least a 44-by-44 CSS-pixel target unless an
  equivalent adjacent control provides the action.
- Keyboard use covers navigation, search, watchlist toggling, stock actions,
  disclosure controls, the V2 Explanation panel, and the Challenge composer.
  Focus never becomes obscured, trapped, or reset unexpectedly after updates.
- Inputs expose labels, required/disabled state, validation feedback, and
  submitting state. Dynamic status, error, and completed-result messages are
  announced without exposing provider internals.
- Text and essential UI boundaries meet WCAG 2.2 AA contrast. Bullish,
  bearish, neutral, warning, and error states use text, iconography, or shape
  in addition to colour.
- Body text, charts, evidence metadata, and controls remain legible at 200%
  browser zoom. Reduced-motion preference removes non-essential transitions
  and streaming decoration without removing state feedback. Motion defaults to
  restrained 160–240 ms transitions; page/card entrance, hover elevation, and
  streaming/replay motion must be reviewed both with and without reduced
  motion.
- Evidence citations, dates, freshness, prices, chart trends, and queue state
  have textual equivalents that do not rely only on placement or colour.

## Visual and device evidence

Before marking a redesigned surface complete, capture a clean Web screenshot
for its normal state at 390 px and 1280 px plus every non-obvious error,
empty, or state-gated interaction in the table above. Record the viewport,
route/screen, data fixture or safe account state, current commit, and known
limitation in the Phase 8 verification record. Never capture credentials,
access tokens, or private user content.

The current record is [`phase-8-verification-record.md`](phase-8-verification-record.md).
It may contain partial evidence; only the documented closure gates permit
Phase 8 to move to Done.

At Phase 8 close, repeat the representative flows on an iOS simulator, an
Android simulator, and at least one physical device. Record OS/device, app
version or commit, executed flow, result, and any limitation. A Web screenshot
is supporting visual evidence only; it does not substitute for native review.

## Staging-release acceptance

Local review is not a release substitute. Before a public-demo update, deploy
frontend and backend from the same immutable Git SHA to a separate staging
environment. Verify the frontend calls the matching `/bundle` contract, then
run the fresh, stale, unavailable, V2 Debate, and responsive checks there.
`review_fixture` remains limited to local or explicitly protected preview
review and must not leak into the public data path. Record both deployment
identifiers and SHA in the verification record. A public demo must not be used
as the first visual acceptance environment.

## Required checks per UI commit

Run the following in order from `apps/mobile`; their order prevents concurrent
Expo exports from sharing `dist`:

```sh
npm run test:stream
npm run typecheck
npm run build:web
```

At the Phase 8 completion boundary, also run the complete backend test suite.
