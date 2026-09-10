# Phase 8 verification record

**Status:** Re-baselined; Phase 8 remains in progress and final visual acceptance is reopened

**Recorded:** 2026-09-08

**Current WP0 baseline revision:** `898e821` (`docs: rebaseline phase 8 design remediation`)

**Historical subject revision:** `118f3d1` (`fix: finish phase 8 accessibility coverage`)

This is an honest acceptance record, not a release sign-off. On 2026-09-06 the
acceptance baseline changed: repository-root `prototype.html` is the required
dark visual reference and the warm-paper implementation is no longer an
acceptable completed design. Consequently, the 2026-08-30 local Web evidence
below remains useful accessibility/regression evidence, but cannot be used as
final evidence that Phase 8 visual design, charts, or Debate experience is
complete. No implementation completion is claimed by this update.

The checks use only deterministic tests or the demo backend and
`EXPO_PUBLIC_AUTH_MODE=demo`; no credentials, external market calls, or model
calls were used.

## WP8 integrated regression baseline on 2026-09-08

WP8 began from revision `1f9adfe`. Luna ran the complete local automated gate
without changing the worktree. Root checked the reported commands and retained
WP8 as in progress until the browser, accessibility, native-simulator, and
physical-device evidence below is resolved.

```sh
cd backend && PYTHONPATH=. .venv/bin/pytest -q  # 369 passing, 1 existing warning
cd ../apps/mobile && npm run test:stream        # 66 passing
npm run typecheck
npm run build:web
git diff --check
```

The mobile count includes the reduced-motion transcript policy committed in
`1f9adfe`. `AccessibilityInfo` supplies the current platform preference; both
direct and frame-scheduled transcript scrolling read the latest value and fail
closed to non-animated movement until the preference is known. A separate Luna
review found and Root fixed a stale-closure race before that commit, then the
reviewer reported no remaining P1/P2 finding in the slice.

### WP8 newly observed recovery issue: active Debate admission conflict

During local review on 2026-09-08, tapping Debate from the stock page sent the
request, but repeated `POST /debates` calls returned `409 Conflict`. The test
user already owned an unfinished Debate in `awaiting_user`. This confirms the
backend's one-active-Debate protection is operating as designed; it is not a
failure of Debate generation or the V2 state proxy.

At discovery, the user-visible failure was an open frontend interaction
problem. The error was rendered only in the stock page's top-level feedback
area, while the Debate action was at the bottom of the page. At the point of
interaction the button therefore appeared not to respond, and there was no
nearby action to open the existing Debate or navigate to History. No frontend
fix or acceptance was claimed by this initial observation.

This case is added to the WP8 recovery matrix. The required follow-up is to
make the conflict explicit near the Debate action, prevent repeated submissions
while the request is pending, and provide an open-current-Debate or History
action. The eventual implementation should be exercised through the
deterministic recovery proxy/API fixture and browser evidence, then included in
the final automated gate. Restarting `review_fixture` or opening the existing
item from History remains a temporary review workaround, not a product fix.

### WP8 recovery implementation update on 2026-09-08

Commit `0e7c813` implements the active-Debate recovery interaction locally. It
preserves the API conflict status, protects against synchronous duplicate
submissions, displays a recovery card near the Debate action, and provides
actions to open the current Debate or navigate to History. The local mobile
gate now reports 72 passing tests; TypeScript typecheck and Web export also
pass.

Commit `8c9278c` adds the V2 transient proxy coverage for reconnect, retry,
cancel, and failure; its focused suite reports 15 passing tests.

Current status for this recovery issue: **Implemented locally / awaiting
product-owner visual confirmation**. Xcode/native simulator review, physical
device review, and final visual acceptance remain outstanding and are not
claimed by these local results.

### WP8 newly observed point-question interaction issue and implementation

Product-owner review found that the former “Challenge this point” action opened
a large composer at the bottom of the transcript and implied that entering a
question would immediately start Round 2. The panel was easy to miss at the
current scroll position and offered no visible Cancel, Back, or backdrop
dismissal. This conflated an educational question with a durable Debate
intervention.

Commit `425104c` makes the deterministic Explanation provider support exact
passages up to the existing 500-character request limit without violating the
100-character term schema, and broadens the Groq prompt from a term to a term,
claim, or passage. Commit `87408ba` changes the message action to “Ask about
this point”, opens a current-viewport read-only Explanation modal by default,
and requires a separate explicit confirmation before calling the Challenge
endpoint. The modal includes Close, Cancel, backdrop dismissal, Android Back,
keyboard avoidance, stale-request protection, and disabled duplicate submit
states. A Terra review found no P0/P1 issue; its Android Back and keyboard
findings were corrected before the final local gate.

The post-fix deterministic gate reports 370 passing backend tests and 78
passing mobile tests; TypeScript typecheck, Expo Web export, and
`git diff --check` pass. Current status: **Implemented locally / awaiting
product-owner simulator interaction confirmation**. The product owner will
perform the page-level visual checks from a concise checklist and report any
failure; engineering will reproduce and modify code. This does not claim iOS,
Android, physical-device, 200% zoom, screen-reader, or final WP9 acceptance.

## WP3 prototype-derived design foundation verification on 2026-09-07

WP3 replaces the shared warm-paper shell with one semantic deep-theme contract
derived from `prototype.html`: navy canvas and layered blue surfaces, teal
constructive/positive states, pink risk states, and gold action/evidence
attention. The contract includes typography, spacing, radius, contrast-safe
content and status colours, focus-ring colour/width, elevated/floating
surfaces, responsive content/navigation sizing, and an explicit reduced-motion
timing selector. Existing fixture, error, accessibility, and provenance copy
remained intact. Stock chart strokes and the existing V2 screen now consume the
same chart/role tokens; this changes visual roles only, not the Stock workspace
information architecture or the Debate conversation layout.

From `apps/mobile`, the following passed after the foundation change:

```sh
npm run test:stream  # 47 passing tests
npm run typecheck
npm run build:web
```

The provenance-aware fixture wording added during visual review was also
covered by the full backend run:

```sh
cd backend && .venv/bin/pytest -q  # 365 passing tests
```

The added token, shell, and accessibility assertions cover the deep canvas and
semantic role mappings, spacing/radius/elevation contract, reduced-motion
durations, 44 px targets, AA contrast for primary/secondary/status and
on-accent text, focus-ring strength, and root-frame/navigation fit at 320,
390, 768, and 1280 CSS pixels.

Using the documented local `review_fixture` backend and demo-auth frontend,
the Web app was then inspected at those four viewports. Every viewport kept
`document.documentElement.scrollWidth` equal to the viewport width; the
floating navigation measured 288 px at 320, 680 px at 768, and stayed centred
at 680 px on 1280. The fixture banner stayed visible, no framework error overlay
or browser console error appeared, and the loaded AAPL workspace retained its
simulated label and rendered price-chart controls. The temporary local servers
were stopped after inspection. This is implementation/regression evidence only:
it does not approve subjective page composition, Stock workspace hierarchy,
V2 chat choreography, native-device appearance, or the final product design.

## WP4 Stock research workspace verification on 2026-09-07

WP4 implements the Stock research layout locally without changing indicator
formulas or the API schema. The pure workspace-layout helper fixes the intended
breakpoint contract: 320 and 390 CSS px use a single reading column; 768 uses
two-up technical/macro chart grids without a sidebar; 1280 uses a primary
price/research column beside a data-readiness and signal-snapshot sidebar.
The phone order is price, snapshot, technical panels, market backdrop, then
actions. Technical panels precede macro context at every size.

Price, technical, and macro SVG components now derive their viewBox from the
measured layout width after a safe first render, rather than retaining a
320-pixel chart coordinate system. The price inspector preserves 1M/3M/6M/1Y
range selection, touch drag, adjustable accessibility actions, Earlier/Later
buttons, selected date/value text, and textual trend equivalents. A daily range
is disabled and empty when its verified/simulated daily curve is unavailable;
weekly-only history defaults to 6M. Per-series availability gates each
technical visual and shows its truthful unavailable state. The volume scale
also handles an all-zero series without invalid numeric SVG attributes.

The provenance helper now fails closed if optional history or availability
metadata is absent: a `daily_market_cache` source string alone cannot make a
daily curve or verified-history claim, and `demo_fallback` never supplies a
daily range. An intraday quote uses the neutral wording “Quote snapshot ·
cached server-side for up to one minute,” rather than asserting market-data
freshness. Fixture label/provenance and catalog/loading/error/unavailable
branches remain in place.

From `apps/mobile`, these local checks passed after the WP4 change and root
review fixes:

```sh
npm run test:stream  # 56 passing tests
npm run typecheck
npm run build:web
```

Focused tests cover all four workspace breakpoints, source-only and
metadata-absent fail-closed provenance, a weekly-only plus `demo_fallback`
conflict, mixed or mode-mismatched history provenance, simulated and
weekly-only history, an all-zero finite volume scale, truthful catalog coverage
labels, and the existing price/indicator math boundaries.

Root then ran the isolated `review_fixture` backend and demo-auth Expo Web app.
At 320/390/768/1280 CSS px the root scroll width exactly matched the viewport.
The AAPL price chart measured 202/260/630/738 px respectively, and each SVG
viewBox adopted the measured width; the first technical cards measured
214/272/300/354 px. The 1280 layout rendered a 320 px readiness/sidebar with
Evidence and Debate actions beside the primary price workspace. The floating
navigation remained 288/346/680/680 px.

On 390 px, Earlier changed the selected point from 22 to 21 and an actual mouse
move over the chart changed it to point 3. Switching to 6M produced a weekly
27-point chart and retained the simulated provenance label. The state matrix
also rendered GOOG stale, NVDA with 19 closes and unavailable MA panels, TSLA
with unavailable price/paused signals, and MSFT as catalog-only without losing
their boundary copy. Two reference screenshots were visually inspected at 390
and 1280; no error overlay or browser warning/error appeared. These results are
Web implementation evidence, not native-device or subjective product-owner
approval; those remain WP8/WP9 gates.

A final clean restart confirmed that the readiness copy now says “Simulated
review history is sufficient” and no longer describes fixture rows as
verified; the 390 px page remained overflow-free with no browser warning/error.
The final entry-path check also distinguishes NVDA and TSLA as “Limited
coverage” while retaining “Watchlist only” for the MSFT catalog-only boundary,
so partial and unavailable research states remain discoverable during review.

## WP5 Debate fact/evidence contract verification on 2026-09-07

WP5 adds a backward-compatible `presentation` projection to each canonical
Debate message record. The server builds it from the immutable Session analysis
context and the persisted, allowlisted citations; the client does not infer
source metadata from an evidence ID. The projection exposes the canonical
argument, cited fact excerpt, interpretation, uncertainty, evidence ID/type,
title, source, date, freshness, optional `support_span`, explicit missing-field
list, and a safe source destination. A destination is exposed only when it is
an absolute public HTTPS URL without embedded credentials; local, private,
relative, non-HTTPS, or malformed destinations become unavailable.

New providers do not yet author an exact claim-to-source `support_span`, so new
citations correctly retain `null`; the evidence excerpt remains a separate
authoritative `fact` field. Existing persisted messages and retained event
payloads remain compatible because presentation is additive and optional. Both
`turn.completed` and `judge.completed` SSE events now include the same
server-authored projection as the detail/message APIs, while an older event
that omits it cannot overwrite an already loaded presentation.

Root verification after integration and review fixes passed:

```sh
cd backend && .venv/bin/pytest -q  # 369 passing, 1 existing Starlette warning
cd apps/mobile && npm run test:stream  # 60 passing
cd apps/mobile && npm run typecheck
cd apps/mobile && EXPO_PUBLIC_AUTH_MODE=demo npm run build:web
```

The focused backend subset passed 99 tests across presentation, orchestrator,
preview API, review fixture, streaming/provider, and memory/Supabase repository
contracts. Tests cover citation order, exact frozen fact content, explicit
missing metadata, source safety, unknown-ID rejection, detail/messages parity,
review-fixture isolation, SSE presentation parity, persisted support spans,
and the client rule that legacy citations never become invented fact details.
WP5 changes the data contract only; expandable fact presentation and the
chronological chat layout remain the separately committed WP6 deliverable.

## WP6 chronological Debate chat verification on 2026-09-07

WP6 replaces the full-width V2 card stack with one responsive chronological
conversation. Bull messages align left, Bear messages align right, User
Challenge messages are centred, and Interim/Final neutral Judge cards are
centred with explicit textual phase labels. Round, exchange, and sequence
markers remain visible. Argument, interpretation, and uncertainty remain
separate, while Facts & evidence expands only the server-authored WP5
presentation. Legacy records explicitly decline to infer fact metadata.

Streaming drafts retain a dashed temporary treatment and are replaced only by
canonical completion. Transcript auto-follow now runs only while the reader is
near the end and coalesces repeated stream/content-size requests into one
animation frame; otherwise a centred “New messages” action is shown. The
source action handles platform rejection with a local visible error. The
header badge reports the Debate phase rather than describing an
`awaiting_user` transport as merely closed. Deterministic fixture terms are
exact substrings of their canonical messages, so the bounded read-only
Explanation panel can be exercised locally.

Root verification after Terra implementation, Luna read-only review, and root
fixes passed:

```sh
cd backend && .venv/bin/pytest -q  # 369 passing, 1 existing Starlette warning
cd apps/mobile && npm run test:stream  # 64 passing
cd apps/mobile && npm run typecheck
cd apps/mobile && npm run build:web
```

Root then ran the isolated `review_fixture` backend and demo-auth Expo Web app.
At 320, 390, 768, and 1280 CSS px, both document and body scroll widths exactly
matched the viewport. At 1280, the 780 px conversation column rendered 530 px
Bull and Bear bubbles at its left and right edges; the 577 px Judge card was
centred. The 320 and 390 captures retained readable role and phase labels,
44 px actions, the permanent simulated-data banner, and the floating
navigation without horizontal clipping.

The AAPL Round 1 fixture rendered six ordered Bull/Bear turns and a centred
Interim Judge. Expanding the first Bull disclosure showed two authoritative
simulated fact excerpts with evidence type, title, source, date, freshness,
and explicit missing `support span`/`source destination` labels; no metadata
was reconstructed from IDs. Selecting an exact term opened the read-only panel
and produced a bounded explanation with the two linked evidence IDs. Selecting
the first Bull argument and submitting a Challenge produced 13 ordered
canonical messages: the centred User Challenge, four Round 2 agent turns, and
the centred Final neutral Judge as the last message. History reopened the
paused Session and the header correctly displayed `ROUND 1 PAUSED`.

The synchronous fixture cannot visually hold transient queued, retry,
reconnect, cancellation, or high-frequency draft states long enough for a
browser screenshot. Their state visibility, cancellation boundaries, late
output rejection, cursor recovery, and draft-to-canonical rules remain covered
by the existing mobile/backend automated suites. Native simulator, physical
device, reduced-motion, zoom, and subjective product-owner approval remain
WP8/WP9 gates.

## WP7 remaining-surface verification on 2026-09-07

WP7 applies the shared Prototype-derived dark grammar to Authentication,
Watchlist/Discovery, Evidence, legacy Claim Examination, History, About, and the
classic Debate fallback. Auth becomes a two-panel desktop surface and a single
mobile flow. Watchlist and catalog become balanced desktop columns. Evidence,
Examination, History, About, and Legacy use the shared 760 px reading measure.
The Legacy route is labelled once at page level, while Bull/Bear/Judge identity
remains the primary card hierarchy.

Root ran the local review fixture and a separately isolated standard demo
profile with demo auth, in-memory persistence, deterministic analysis, disabled
market credentials, and V2 explicitly off. At 320, 390, 768, and 1280 CSS px,
Auth, Watchlist, Evidence, Examination, About, and Legacy had document scroll
width equal to viewport width. At 1280, Evidence and History used the 760 px
reading measure. Browser flows verified catalog-only MSFT search; the three-item
AAPL Evidence Board; empty and Interim-Judge History; expanded About technical
details; classic analysis generation; Bull claim examination and its evidence;
and a reopened Legacy History row.

The evidence action accepts only credential-free public HTTPS destinations. It
rejects whitespace, local/private/shared/reserved/multicast IPv4, all IPv6
literals (conservatively, including mapped and 6to4 forms), `.localhost`,
`.local`, and `.internal`. Auth Web inputs expose independent label,
description, required, and invalid state for email and password; the browser
DOM check confirmed a valid email remained valid while a short password linked
to its own error text. No live market/model/auth request, deployment, or remote
write was used for this evidence.

After Terra and Luna implementation, Root browser review, and Sol read-only
audit fixes, the final Sol re-review reported no remaining P1/P2 findings. The
complete local gates passed:

```sh
cd backend && .venv/bin/pytest -q  # 369 passing, 1 existing warning
cd apps/mobile && npm run test:stream  # 65 passing
cd apps/mobile && npm run typecheck
cd apps/mobile && npm run build:web
git diff --check
```

Not yet closed: live-auth submission outcomes, every discovery/error/retry
state, all four legacy question types and controlled failure, 200% zoom,
reduced motion, native screen readers/simulators, one physical device, staging,
current-data verification, and subjective product-owner approval. These are
WP8/WP9 gates.

## Automated baseline

From `apps/mobile`, the following passed at the subject revision:

```sh
npm run test:stream  # 36 passing tests
npm run typecheck
npm run build:web
```

The restored CI-equivalent backend entry point also passed:

```sh
cd backend
pytest -q  # 345 passing tests
```

The Web export built successfully. The focused tests cover all required CSS
widths, navigation target fit, focus-ring token strength, AA contrast for
small positive-state labels, and the 44 px interaction-target token used by
the corrected chart and Debate controls.

## WP1 market-data and indicator verification on 2026-09-07

WP1's automated implementation checks use local fakes and MockTransport; they
do not contact Supabase or a market provider. The implementation adds the canonical contract in
[`phase-8-indicator-contract.md`](phase-8-indicator-contract.md) and preserves
the existing numeric indicator fields while adding explicit history and
per-series availability metadata.

From `backend`, the complete suite passed:

```sh
.venv/bin/pytest -q  # 359 passed, 1 existing Starlette/httpx warning
```

From `apps/mobile`, all client gates passed:

```sh
npm run typecheck
npm run test:stream  # 42 passed
npm run build:web
```

`git diff --check` also passed. Focused tests prove the mirrored backend/client
golden vector, Wilder RSI including the flat-series case, full-window MA20 and
MA50, MACD/signal warm-up, 20-session annualised log-return volatility, 49/50
complete-view boundary, duplicate/out-of-order/future-close rejection,
source-only false-complete rejection, latest-100 Supabase read order, failed
ingestion exit, and non-advancing refresh exit.

The old Supabase read requested `trading_date.asc` with `limit=100`, which can
freeze an accumulating table on its oldest 100 rows. WP1 requests the newest
100 rows descending and restores chronological order in memory. No database
schema change was needed. No live AAPL refresh or remote write was run, so the
previously observed hosted-cache freshness remains an open deployment check
rather than being inferred from passing local tests. During an additional
manual API-shape check, the local `.env` unexpectedly selected the configured
Supabase store and issued one read-only AAPL bundle GET. It returned cache data
but made no write, exposed no secret, and called no market or model provider.
That accidental read is recorded for transparency and is excluded from WP1
acceptance evidence.

The strengthened review also proves that simulated `review_fixture` history can
render its labelled curve without becoming verified market data, stale verified
history stays inspectable with a warning, valid weekly history remains available
when daily history is insufficient, missing or invalid OHLCV degrades safely,
empty ticker selection fails, and a mocked Supabase write must pass a post-write
latest-date check. A non-advancing result may reflect a market holiday or stale
provider response; it remains deliberately nonzero because the freshness gate
cannot prove advancement.

## WP2 isolated review-fixture verification on 2026-09-07

The local-only `APP_DATA_MODE=review_fixture` profile was exercised without
credentials or external requests. Its settings validator overrides any
Supabase, model, auth, Queue, Redis, or quote-provider values inherited from
`.env`; production-like environments reject the mode rather than selecting it.
The API returned a deterministic AAPL fresh scenario, GOOG stale scenario,
NVDA 19-record insufficient scenario, TSLA unavailable-price scenario, and
MSFT catalog-only identity. AAPL's bundle contained seven dated macro series,
all marked with simulated metadata. Daily and weekly fixture rows use the
explicit `review_fixture` source, while Alpha Vantage remains reserved for
real weekly cache rows.

Focused local checks passed:

```sh
PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests/test_review_fixture.py  # 5 passed
```

The complete local regression also passed: `364` backend tests, `44` mobile
tests, TypeScript, and Expo Web export. The frontend run explicitly set
`EXPO_PUBLIC_AUTH_MODE=demo`, so the configured root `.env` could not construct
or refresh a Supabase client during fixture review.

The no-outbound test patched HTTP clients and exercised the AAPL bundle,
analysis, macro context, and catalog/unavailable boundaries. A direct
`TestClient` run with `APP_DATA_MODE=review_fixture` also returned `data_mode`
as `review_fixture`, `provider=demo`, no quote, seven macro contexts, and
`history.provenance=review_fixture`. This proves local mode selection and
provenance boundaries, including a complete deterministic V2 Round 1 preview
with simulated news and filing citations. Retry, reconnect, cancellation, and
responsive/native/physical-device visual review remain later acceptance work;
this package does not alter those state-machine contracts.

Root then ran the documented backend/frontend command pair and inspected the
actual Web UI at 390 px. The global simulated-data banner remained visible on
Watchlist, stock research, and Debate; document width matched the viewport with
no error overlay or console warning. AAPL visibly rendered its daily price
curve, MA20/MA50, RSI, MACD, volume, realised volatility, and all seven macro
series. The Earlier control changed the selected point, and 6M switched to the
simulated weekly series without claiming Alpha Vantage provenance. The V2 flow
advanced from seven canonical Round 1 messages through an exact-text Challenge
to 13 canonical messages and a Final Neutral Judge; displayed citations used
only `review-aapl-*` fixture IDs. Backend logs for that run contained only the
expected localhost API requests. This is WP2 functional evidence, not approval
of the still-warm visual design; Prototype dark-theme migration starts in WP3.

## WP0 browser characterization on 2026-09-07

Root ran Expo Web at `http://localhost:8081` against a local FastAPI backend
with demo authentication, demo persistence, deterministic analysis, V2 off,
and Queue off. This establishes a reproducible pre-redesign baseline; it is not
approval of the current visual direction.

| Surface / viewport | Result | Characterization evidence |
| --- | --- | --- |
| Watchlist, 390 px | Pass as functional baseline | The catalog and saved AAPL row rendered with meaningful accessible text. No browser error overlay or console warning appeared. The warm-paper layout is explicitly not the accepted Phase 8 visual result. |
| Watchlist, 1280 px | Pass as functional baseline | Catalog, Watchlist controls, and bottom navigation rendered; document width equalled viewport width with no page-level horizontal overflow. The composition remains visually sparse and warm. |
| AAPL workspace, 1280 px | Expected current limitation reproduced | A quote was present, followed by a stale-history warning, “No curve is shown until market data is verified,” and paused RSI/MACD. This proves the reported missing-chart experience is a current gate outcome, not a missing route. |
| Legacy Debate, 1280 px | Expected current limitation reproduced | Snapshot, Judge, Bull, and Bear appeared as a vertical stack of wide cards. The accepted Bull-left/Bear-right chronological V2 chat was not present because the baseline flags deliberately retained Legacy. |

The demo-mode AAPL workspace labelled its displayed quote as a Finnhub quote
dated 2026-09-04, while the generated Legacy Debate snapshot used a 2026-02-25
close and a different value. WP0 treats this as evidence that the current demo
fallback/provenance presentation is ambiguous; neither value is asserted to be
live market data. Browser screenshots were visually inspected but not committed
and contained no credentials or private user content.

## Historical Web browser verification (superseded as final visual evidence)

The local deterministic Web demo was checked in Chromium with the live FastAPI
demo backend.

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| 320, 390, 768, and 1280 CSS px | Pass | No horizontal document overflow at each width. At 1280 px the bottom-navigation content measured 1160 px, rather than filling the viewport. |
| 200% reflow | Pass with tooling limitation | A 640 CSS-px viewport was used as the 1280 px / 200% reflow equivalent; the CLI cannot drive Chromium's browser-UI zoom control directly. |
| Keyboard navigation and focus | Pass | Watchlist → Signals follows Tab order, and the focused tab exposes the 3 px focus border. Auth fields and enabled actions follow Email → Password → Sign in → Create account. |
| Reduced motion | Pass | `prefers-reduced-motion: reduce` was active while the page rendered. |
| Screen-reader semantics | Pass for checked flows | Accessibility snapshots exposed tab roles, selected tab state, search labels, Watchlist actions, empty History, About headings, and the technical-details disclosure. |
| Contrast | Pass | axe-core 4.12.1 at 320 px reported 0 violations, 0 incomplete checks, and 22 passes after the Watchlist token correction. |
| Web screenshots | Captured locally | Clean 320/390/768/1280 Watchlist captures, 320 empty History/About/disclosure captures, and a reduced-motion capture were taken against the deterministic fixture. They are local verification artifacts and deliberately not committed. |

The Supabase-configured Web entry was also opened without entering or submitting
credentials. Its 320/390/768/1280 layouts had no horizontal overflow and its
initial axe audit had 0 violations. This did not establish that data was fresh,
that charts/indicators were inspectable, that the frontend and backend were
deployed together, or that the V2 transcript met the re-baselined design.

## Simulator review

| Target | Result | Executed flow | Limitation |
| --- | --- | --- | --- |
| Android Emulator — Pixel (`emulator-5556`, `sdk_gphone16k_arm64`) | Partial pass | Chrome opened the local deterministic Web bundle through `10.0.2.2`; catalog/watchlist data loaded, source/freshness wording remained visible, and direct taps reached About and the empty History. Android's accessibility tree exposed all four bottom-navigation labels and the About disclosure. On 2026-08-30 the locally installed Expo CLI resolved the SDK 52 client as Expo Go 2.32.20 and attempted its official Expo GitHub APK download for 90 seconds. | This is Android Chrome running the Expo Web bundle, not the native Expo Go/standalone app. The APK download produced no progress or cache file, so it was stopped without installing anything. Chrome's own Translate prompt appeared once and was not treated as application UI. |
| iOS Simulator — iPhone 17 Pro, iOS 26.5 | Blocked | Simulator booted; the installed-app inventory contained no Expo Go client. | Safari's earlier first-run Start Page onboarding obscured the Web check, and no native Expo client or standalone app is installed. No app-page result is claimed. |
| Physical device | Not run | No physical iOS or Android device was connected to the workstation. | Required before Phase 8 can close. A device must be unlocked, developer/USB-debugging enabled where applicable, and able to reach the local backend through the workstation LAN address (not `10.0.2.2`). |

Android screenshots were visually inspected after data loaded and after About and
History navigation. They showed a single-column layout, a persistent bottom
navigation bar, visible source/freshness wording, and no application error
banner in the successful demo run.

## Findings recorded on 2026-09-06

- The current application retains a warm global theme while V2 Debate carries
  a separate dark theme; shared dark semantic tokens and component adoption are
  still required.
- The root Prototype establishes deep navy surfaces with teal Bull, pink Bear,
  and gold Evidence/Judge, but it must be adapted to live content and desktop
  layouts rather than copied as a fixed phone frame.
- The current visual evidence does not cover complete technical trends. The
  `demo_fallback` path intentionally protects users from synthetic data being
  mistaken for market data, but it also prevents a complete local chart review
  in its current form.
- A labelled deterministic `review_fixture` is required for UI acceptance;
  fallback, simulated review data, stale live data, and unavailable data must
  be distinguishable.
- V2 contains the underlying message/evidence concepts, but the current
  acceptance evidence does not show a left/right chronological chat transcript
  with centred interim/final Judge summaries or expandable fact/citation
  detail.
- The prior review did not prove a common frontend/backend definition for the
  displayed RSI and volatility values.
- Public-demo deployment cannot be treated as the first acceptance target:
  frontend and backend must be staged and verified from the same Git SHA.

## Reopened closure gates

- Implement and review the shared Prototype-derived dark design system across
  the app. Confirm that no warm-paper production surface remains and that
  desktop adapts beyond the phone-frame reference.
- Provide the explicitly labelled local `review_fixture`, then visually review
  complete price and eligible technical-indicator curves alongside fresh,
  stale, unavailable, and `catalog_only` states. Verify per-indicator minimum
  history thresholds and one shared RSI/volatility definition.
- Rework and review V2 Debate as a chronological chat transcript: Bull left,
  Bear right, mobile chronological offsets, centred interim/final neutral
  Judge, distinct user Challenge, and no unwanted forced auto-scroll.
- Review fact output and actionable citation detail: value, date, source,
  freshness, support span where available, and original link. Preserve
  provenance, default-off V2/Groq Explanation, read-only Explanation, and
  `awaiting_user`-only Challenge.
- Capture new Web evidence at 320, 390, 768, and 1280 px, 200% zoom, and both
  normal/reduced-motion settings for the redesigned Stock and V2 Debate flows.
- Run the actual managed Expo app or a standalone/dev build on both iOS and
  Android simulators; a browser bundle is supporting evidence only.
- Run the representative flow on at least one physical device and record its
  OS/device, commit, screenshot, flow, and result.
- Deploy frontend and backend from the same immutable SHA to staging. Verify
  the matching `/bundle` contract, data-state labelling, V2 states, and
  responsive flows there before any public-demo release.
- Re-run the complete backend suite and all Phase 8 acceptance checks after
  implementation; only then may the phase be evaluated for Done.

## 2026-09-09 — WP8L quote/completed-close snapshot checkpoint

Root reviewed the Sol snapshot slice and corrected quote retrieval provenance
on cache hits and freshness evaluation against the capture-time market session.
The staged files were exported with `git checkout-index` into a temporary clean
directory, excluding unfinished reveal/Judge/offline-preflight work. Running
`backend/.venv/bin/python -m pytest backend/tests -q` against that exact staged
snapshot passed **374 tests**, with one existing Starlette/httpx deprecation
warning. `git diff --cached --check` passed.

The passing scope is immutable market inputs and fail-closed market admission,
not complete Live Acceptance. Holiday/early-close calendars, evidence/filing/
macro admission, client snapshot display, streaming Judge, reveal integration,
Stop/interjection, provider quota checks, native-device and staging acceptance
remain open. Uncommitted work for later slices is intentionally excluded from
this checkpoint; validate it before using the shared working tree as a runtime.

## 2026-09-09 — Offline capture audit checkpoint

Added eight offline tests for valid capture, page/history/indicator disagreement,
missing quote provenance, stale/future evidence, malformed dates, duplicate
macro codes, capture-time close validation, and redacted nonzero CLI failures.
The staged snapshot was exported to a clean temporary directory, excluding
unfinished Judge/reveal work. Full backend suite: **382 passed**, one existing
Starlette/httpx deprecation warning. `git diff --cached --check` passed. No
external data refresh, model call, database write, or deployment occurred.

## 2026-09-09 — Live evidence eligibility checkpoint

The staged snapshot was exported with `git checkout-index` to a clean temporary
directory, excluding all unfinished Judge/reveal work. Full backend suite:
**393 passed**, one existing Starlette/httpx deprecation warning. Coverage adds
source-window boundaries, forged freshness labels, future/malformed dates,
ticker/source provenance, invalid URLs, duplicate IDs, immutable selection,
and integration with live snapshot creation/409 rejection. `git diff --cached
--check` passed. No provider refresh, model call, database write, or deployment
occurred. Macro and structured financial-fact admission remain open.

## 2026-09-09 — Live macro eligibility checkpoint

The staged snapshot was exported with `git checkout-index` into a clean
temporary directory, excluding unfinished Judge/reveal changes. Full backend
suite: **406 passed**, one existing Starlette/httpx deprecation warning.
Thirteen new validator cases cover identity, units, metadata, invalid/future/
stale dates, timezone requirements, non-finite values, missing/duplicate series,
ordering, immutability, and the inclusive age boundary; snapshot integration
also checks missing-macro 409 behavior. `git diff --cached --check` passed.
No provider refresh, model call, database write or deployment occurred.

## 2026-09-09 — Structured financial inputs

Isolated staged snapshot: **418 backend tests passed**, one existing warning.
New tests cover ticker-scoped public REST query bounds, SEC lookalike-host
rejection, periods, stale/future values, duplicate conflicts, revision selection
and live-context integration. Full regression caught and resolved an accidental
bundle reference before commit. No model calls or database writes in this slice.

## 2026-09-09 — Human-visible reveal pacing

Mobile scheduler separates received/revealed content, retains word/grapheme
boundaries with pinned `unicode-segmenter`, delays canonical display until
reveal drains, and serializes visible agent bubbles. Long backlogs accelerate
in bounded increments rather than jumping to the full response. History,
reconnect, reduced-motion, screen-reader and background settlement bypass typing.
Root corrected timer starvation under rapid SSE updates and kept missing-delta
exceptions restricted to the existing non-streaming Judge. Terra reviewed
canonical ordering and durable-record precedence. **91 mobile tests**, typecheck
and Web export passed. Native accessibility/device review remains outstanding;
this slice does not implement the new Stop/interjection contract.

## 2026-09-09 — Streaming Judge integration and controlled probes

**424 backend tests passed**, one existing warning. Mocked Groq Judge coverage
checks ordered text, citations, output bounds, usage, separate safe defaults and
completion cap. Orchestration coverage checks Judge deltas, model/usage metadata,
job totals, and cancellation with no persisted summary or false failure.
Provider streams close on error/cancellation. Review removed unsupported
first/second-sentence categorization into agreement/disagreement fields.

Live evidence: Models API confirmed configured model availability; synthetic
Judge attempts capped 200/200 tokens failed normal-completion validation.
After a tighter prose budget, one cap-400 attempt succeeded: 92 deltas, one
citation, 472 prompt/140 completion tokens. Earlier failed-attempt usage is
unknown and excluded from the successful total. No full Live AAPL session ran.
One EIA request refreshed 10 WTI rows; readback latest remained 2026-09-01.
Supabase read-only financial check found 155 cached facts, newest filed
2026-07-31. No deployment flags or schema were changed.

## 2026-09-09 — Live evidence recovery and matching AAPL capture

Read-only diagnostics found stale news and a current 16,071-character filing
rejected by the 6,000-character context bound. Admission now creates an explicitly
marked bounded excerpt without modifying the original document. One Apple
Newsroom RSS request wrote four documents (latest 2026-09-08T13:59:40.685Z).
Offline comparison now permits the research page's larger evidence set while
requiring every selected document's source/date/URL and excerpt prefix to match.
20 focused tests pass, including original-text preservation.

One Finnhub quote request produced a standard AAPL input capture that passed all
16 offline checks: 100 daily rows, two eligible evidence documents, seven macro
series, close date 2026-09-04 and quote as-of 2026-09-08T20:00:00Z. No Session/Job
or model generation was created. Capture JSON stays in ignored `.pytest_cache`.
The earlier expectation that WTI would necessarily fail was corrected: evaluated
at actual UTC capture time, its September 1 observation is within the inclusive
seven-day policy. The EIA refresh did not advance it. This does not prove an
authoritative holiday calendar or newest upstream daily-close availability.


### 2026-09-09 — WP8L interruption foundation

Implemented default-off `DEBATE_INTERRUPTIONS_ENABLED`: checkpoint generated text before publishing each delta and accept an owner/generation-scoped `/debates/{id}/interrupt` request. The repository atomically rotates the generation, preserves the exact visible prefix as incomplete (including trailing whitespace), removes later messages and cancels queued jobs. Running workers acknowledge cancellation and retain observed request usage. Completed output can also be shortened when display is still catching up. Repeated identical requests are idempotent; invented prefixes and stale generations are rejected.

Validation: backend suite 434 passed (one existing Starlette/httpx deprecation warning); regression coverage includes API flag/ownership, exact prefix, late provider output, canonical completion before interruption, and repeat requests. No market or model calls in this step.

Limitations: SQL migration `20260909_debate_draft_interruption.sql` is authored but NOT applied or PostgreSQL-runtime validated. Checkpointing currently performs one synchronous persistence write per delta and needs hosted latency measurement. Client Stop here, user interjection and explicit continuation remain pending; this is not WP8L.5 acceptance. Feature stays disabled until migration and end-to-end checks pass.


### 2026-09-09 — WP8L client Stop here integration

Added default-off `EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED`. While a message is revealing, Stop here freezes the last rendered prefix immediately, stops the local stream and submits that exact prefix to `/interrupt`. Failure keeps the display frozen and permits an identical retry; only a matching incomplete canonical response releases the local freeze. Reconnect, accessibility settlement, Show full and late provider completion cannot expand frozen text. Incomplete records explicitly say “Stopped here · Incomplete response” and render raw retained content without old full-text presentation sections.

Validation: mobile TypeScript check passed; 93 Node tests passed, including rendered-vs-received prefix and stale presentation regression; Expo Web export with the interruption flag enabled passed. This is build/unit verification, not browser or Expo Go device acceptance. No market/model calls or persisted environment changes.

Remaining: hosted migration/runtime verification, persistence latency, interruption before the first draft arrives, recovery of an unconfirmed stop after app termination, and user interjection/explicit continuation. The flag remains false in `.env.example`; do not claim the entire Stop here contract is complete.


### 2026-09-09 — roadmap reconciliation at code baseline 50d9885

Documentation-only review reconciled the current-status table and WP8L/setup/
parent-plan acceptance gates with implemented data, Judge, reveal and Stop
foundations. Added `wp8l-next-steps.md` as the ordered remaining-work map through
WP9/WP10 and Phase 9. Explicit additions: server admission versus local freeze,
already-dispatched usage retention, interrupted waiting state, SQL runtime and
checkpoint latency, first-delta/app-termination recovery, frozen-input Continue,
and shared event delivery beyond durable checkpoints. No live provider, database
mutation, deployment or business-code change. Local document links and
`git diff --check` verified; existing test totals are recorded evidence from the
code baseline, not a new test run for documentation edits.


### 2026-09-09 — interruption waiting state

Stop now persists `interrupted_awaiting_user` with no terminal timestamp and
publishes its own event. Terminal Cancel stays distinct and can explicitly end
the paused session. API/SSE/client types and labels recognize the waiting state;
Worker cancellation/recovery preserves it rather than treating it as a failed or
completed round. This state does not itself enable interjection or Continue.
Backend 435 tests and mobile typecheck pass; SQL runtime validation is ongoing
in isolation and the feature remains off. No live data/model calls.


### 2026-09-10 — isolated PostgreSQL and crashed Worker verification

Added `scripts/validate_debate_interruption_sql.sh` and SQL fixtures, using a
temporary local PostgreSQL 17 cluster over a Unix socket (no hosted writes).
Fixed the checkpoint RPC CASE-expression syntax found by execution. First and
repeat migration application, role/RLS isolation, foreign keys, prefix retention,
idempotence and checkpoint pruning pass. The runner supports PG_BIN discovery
and a TMPDIR containing spaces. Worker tests: 12 passed, including Stop followed
by process crash and lease redelivery; the old job is cancelled while the waiting
session and incomplete prefix survive. Per-message audit loss was confirmed and
is being addressed separately by the provider-attempt ledger, not declared fixed
by this migration test. Hosted PostgREST/Queue validation remains separate.


### 2026-09-10 — persisted unconfirmed Stop recovery

The mobile client now persists account/session-scoped pending Stop targets and
visible-message IDs before sending the network request, after freezing locally.
Reopening checks storage before starting SSE or displaying received text. It
restores only the saved visible prefix/history; exact incomplete canonical
confirmation clears the matching pending request. Logout/account changes clear
that account's pending records; stale confirmations cannot remove newer keys.
Empty prefixes, Unicode code-point bounds, corrupt/legacy records and prototype
keys are covered. Frozen drafts are labelled as unconfirmed Stop and cannot Show
full. A remote interruption event reloads the shortened canonical transcript.
Mobile tests: 105 passed; TypeScript passed; Expo Web export passed before the
final label-only refinement. Native kill/reopen is still user-operated acceptance.
No new external data/model calls and no hosted flags changed.
