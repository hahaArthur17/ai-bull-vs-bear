# Phase 8 verification record

**Status:** Re-baselined; Phase 8 remains in progress and final visual acceptance is reopened

**Recorded:** 2026-09-07

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
