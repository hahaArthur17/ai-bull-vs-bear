# Phase 8 UI acceptance matrix

**Status:** Active for Phase 8  
**Owner:** Mobile application  
**Last updated:** 2026-08-30

This matrix is the visual and interaction acceptance contract for the
financial-research UI redesign. It supplements executable checks; it does not
replace the existing API contracts, provenance rules, or Phase 7 interaction
boundaries.

## Product direction

The interface should feel like a calm, information-dense research workspace:
clear market hierarchy, quiet neutral surfaces, purposeful bullish/bearish
signals, and readable evidence before visual decoration. Colour must never be
the sole carrier of financial direction, freshness, job state, or validation
feedback. The same semantic components and content hierarchy must work on
native mobile and Expo Web.

Every redesign slice must preserve these product invariants:

- `catalog_only` securities remain identity-only and never initiate market-data
  or model calls.
- Source, evidence date, freshness, coverage, and warnings remain visible
  wherever analysis is presented.
- V2 Debate and the Groq Explanation provider stay default-off. Explanation is
  read-only and cannot mutate Debate state.
- Challenge is available only during the durable `awaiting_user` pause; it is
  not a general transcript branching affordance.
- Diagnostic/provider implementation detail is progressively disclosed and is
  never the primary status copy for a user.

## View and state coverage

| Surface | Required states to review | Acceptance evidence |
| --- | --- | --- |
| Authentication | initial form, invalid input, submit disabled, submitting, authentication failure, sign-up confirmation | Inputs are labelled; errors are announced and tied to the affected field; submit cannot duplicate a request. |
| Discovery and Watchlist | saved list, empty list, search in progress, search results, no results, search failure, `catalog_only`, `debate_ready` | Search and watchlist controls retain clear names; coverage labels have text as well as visual treatment; empty and failure states provide a recovery action. |
| Stock research workspace | bundle loading, bundle failure, normal quote, stale/warning evidence, watchlist add/remove, `catalog_only` | Quote time, source, evidence date, freshness, and all warnings remain readable; an identity-only security has no analysis CTA. |
| Charts and technical signals | normal data, no data, narrow layout, keyboard/focus interaction where controls exist | Chart values have a textual summary; legends and trends do not depend on colour alone; layout does not horizontally overflow. |
| Evidence and Examination | evidence list, missing/partial evidence, claim selected, examination loading, result, request failure | Each evidence item retains source, date, freshness, and link/identifier; loading and error copy do not imply a completed answer. |
| Legacy Debate | idle/start, active stream, completed transcript, error | Existing start and transcript behavior remains available until shared presentation is adopted; evidence provenance remains legible. |
| V2 Debate | queued, running, retry delay, failed, cancelled, `awaiting_user`, final; connection recovery; explanation closed/loading/result/error | Only canonical messages read as durable; drafts are visually and textually temporary; cancel and retry availability match state; Challenge is enabled only in `awaiting_user`; Explanation does not alter Debate. |
| History | empty, analysis item, V2 active item, interim Judge, final Judge, load failure | Final and interim Judge states remain distinct; reopening a saved session restores its matching ticker bundle. |
| About and diagnostics | normal content, sign-out available, diagnostic disclosure expanded | Product guidance precedes technical detail; any disclosure has an accessible name and state. |

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
  and streaming decoration without removing state feedback.
- Evidence citations, dates, freshness, prices, chart trends, and queue state
  have textual equivalents that do not rely only on placement or colour.

## Visual and device evidence

Before marking a redesigned surface complete, capture a clean Web screenshot
for its normal state at 390 px and 1280 px plus every non-obvious error,
empty, or state-gated interaction in the table above. Record the viewport,
route/screen, data fixture or safe account state, current commit, and known
limitation in the Phase 8 verification record. Never capture credentials,
access tokens, or private user content.

At Phase 8 close, repeat the representative flows on an iOS simulator, an
Android simulator, and at least one physical device. Record OS/device, app
version or commit, executed flow, result, and any limitation. A Web screenshot
is supporting visual evidence only; it does not substitute for native review.

## Required checks per UI commit

Run the following in order from `apps/mobile`; their order prevents concurrent
Expo exports from sharing `dist`:

```sh
npm run test:stream
npm run typecheck
npm run build:web
```

At the Phase 8 completion boundary, also run the complete backend test suite.
