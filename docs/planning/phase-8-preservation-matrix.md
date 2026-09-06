# Phase 8 Functional Preservation Matrix

**Status:** WP0 baseline complete

**Recorded:** 2026-09-07

**Baseline revision:** `898e821` (`docs: rebaseline phase 8 design remediation`)

**Parent:** [`phase-8-design-remediation.md`](phase-8-design-remediation.md)

**Visual reference:** [`../../prototype.html`](../../prototype.html)

## Purpose and reading rule

This is the WP0 characterization inventory for the Phase 8 functional
preservation contract. It identifies where a behavior currently lives, which
automated checks provide evidence, and which user-facing proof is still
required before redesign work can be accepted.

“Implemented” means that a code path or automated contract exists. It does not
mean that the current UI matches the Prototype, that the behavior has passed a
real browser/device review, or that a deployed environment has the same
contract. “Partial” means the behavior is present but has a known coverage,
state, or evidence gap. “Unverified” means the implementation may exist but
WP0 has no sufficient automated or manual characterization evidence yet.

The current automated references are test names, not claims that the entire
feature is covered. Each later work package must retain the listed regression
targets and add the missing manual evidence before changing its presentation.

## Preservation matrix

| Feature / required states | Status at WP0 | Main implementation files | Existing automated evidence | Manual evidence still required | Later WP owner |
| --- | --- | --- | --- | --- | --- |
| **Authentication**: sign in, sign up, validation, disabled/submitting, failure, confirmation, sign out, session restore | Partial | `apps/mobile/App.tsx`, `apps/mobile/src/AuthScreen.tsx`, `apps/mobile/src/authState.ts`, `apps/mobile/src/supabase.ts`, `backend/app/services/auth.py`, `backend/app/main.py` | Mobile `authState.test.ts` (`authentication submission state belongs only to the submitted action`); backend `test_auth.py` bearer extraction, valid verifier, invalid-token rejection; App auth gating is exercised indirectly by typecheck/build | Run configured-auth Web flow and native flow: invalid fields, disabled buttons, submitting state, provider failure, sign-up confirmation, sign-out, reload/session restore, safe error wording and keyboard/SR labels | WP3 Terra (theme/accessibility); Root owns auth regression gate |
| **Discovery**: debounced catalog search, no-result/failure recovery, company identity, exchange/sector metadata, coverage status | Implemented, visual unverified | `apps/mobile/src/screens/WatchlistScreen.tsx`, `apps/mobile/App.tsx`, `apps/mobile/src/discoverySummary.ts`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/services/stock_catalog.py`, `backend/app/services/demo_store.py` | `discoverySummary.test.ts` covers loaded/search/clear/rapid-query behavior; backend `test_stock_catalog.py`, `test_demo_stock_catalog.py`, `test_api.py` search cache, Redis outage, bounded catalog search and no external request; `test_stock_coverage_contract.py` validates coverage enum | Capture empty, searching, results, no results, failure/retry and mixed `debate_ready`/`catalog_only` results at 390/1280px; verify labels and opening identity metadata do not imply research coverage | WP3 Terra (foundation); WP7 Terra/Luna (screen migration and regression evidence) |
| **Watchlist**: add/remove, persistence, empty state, and `catalog_only` support without market/model calls | Implemented, boundary needs replay evidence | `apps/mobile/src/screens/WatchlistScreen.tsx`, `apps/mobile/App.tsx`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/services/demo_store.py`, `backend/app/services/supabase_store.py` | Backend `test_demo_stock_catalog.py::test_demo_watchlist_accepts_catalog_only_ticker`; `test_api.py` watchlist/analysis flow, catalog-only save and identity-only boundary; UI action and empty rendering are covered by typecheck/build but have no component test | Verify add/remove survives reload and sign-out/in, empty list recovery, catalog-only can be saved, saving does not trigger `/bundle`, quote, evidence, macro or model calls; check target size and focus | WP2 Terra (fixture boundary); WP3 Terra (foundation); WP7 Terra/Luna (screen migration); Root owns no-call assertion |
| **Stock workspace**: bundle loading/failure, current quote, provenance, freshness, warnings, watchlist action, `catalog_only` boundary | Partial: code exists; current verified-history gate intentionally hides curves/signals for stale/unverified data | `apps/mobile/src/screens/StockDetailScreen.tsx`, `apps/mobile/src/stockDetail.ts`, `apps/mobile/src/stockResearchSummary.ts`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/services/market_data.py`, `backend/app/services/demo_store.py` | `stockDetail.test.ts` verifies saved Debate ticker reload and catalog-only avoids bundle; `stockResearchSummary.test.ts` verifies quote source/timestamp, stale warning and demo fallback unavailable; `test_api.py` verifies bundle cache, quote, catalog-only boundary; `test_market_data.py` parses/normalizes providers and quote cache | AAPL normal/stale/unavailable/fixture states at 390/1280px; confirm price, source, observation time, stale warning, curve boundary and retry; verify bundle failure is visibly recoverable and no simulated price is mistaken for live | WP1 Sol (data contract); WP2 Terra (fixture); WP4 Terra with Sol review |
| **Technical exploration**: 1M/3M daily and 6M/1Y weekly ranges, moving averages, RSI, MACD, volume, volatility, textual summaries, unavailable states | Partial: chart/math paths exist, but frontend/backend formulas and sufficiency contract are not yet unified | `apps/mobile/src/screens/StockDetailScreen.tsx`, `apps/mobile/src/research/chartMath.ts`, `apps/mobile/src/chartMath.test.ts`, `backend/app/services/indicators.py`, `backend/app/providers/technical_factors.py`, `backend/tests/test_indicators.py`, `backend/app/main.py` | `chartMath.test.ts` covers gaps, trailing windows, fixed domains and trend summaries; backend `test_indicators.py` checks expected fields; `test_market_data.py` separates daily/weekly parsing; stock summary/API tests cover stale/fallback presentation | For each range and each series, inspect plotted value, legend, date/value tooltip, selected point, partial history and no-data state by touch/keyboard/pointer at 390/1280px; compare displayed RSI/volatility against backend golden values; verify no page overflow and readable text alternative | WP1 Sol (canonical formulas/sufficiency); WP4 Terra (chart interaction); Root signs off cross-layer equality |
| **Macro exploration**: all seven dated macro series and source/freshness presentation | Partial: bundle and panel support series, but no complete UI/device evidence for all seven | `apps/mobile/src/screens/StockDetailScreen.tsx`, `apps/mobile/src/research/chartMath.ts`, `backend/app/main.py`, `backend/app/services/macro_data.py`, `backend/app/providers/macro_factors.py`, `backend/tests/test_macro_data.py`, `backend/tests/test_api.py` | `test_macro_data.py` covers FRED/EIA normalization, provider-key requirement, malformed payload and provider/display-code separation; `test_api.py::test_macro_context_endpoint_groups_cached_observations`; chart math tests cover generic chart behavior | With a fixture containing S&P 500, VIX, effective rate, 2Y/10Y/30Y Treasury and WTI, verify dates, source, units, latest observation, explanatory copy and missing-series state at phone/desktop widths; verify macro does not claim causation | WP2 Terra (complete deterministic fixture); WP4 Terra (surface); Sol reviews provenance |
| **Evidence board and evidence presentation**: partial/missing evidence, citation metadata, freshness and links | Implemented, citation detail incomplete for V2 | `apps/mobile/src/screens/EvidenceScreen.tsx`, `apps/mobile/src/evidencePresentation.ts`, `apps/mobile/src/components/debate/EvidenceCitation.tsx`, `apps/mobile/src/components/debate/AnalysisSnapshotCard.tsx`, `backend/app/schemas.py`, `backend/app/services/evidence_freshness.py`, `backend/app/services/evidence_ingestion.py` | Mobile `evidencePresentation.test.ts` preserves source/date/freshness and explicit stale/missing dates; backend `test_evidence_freshness.py` covers current/stale/unknown eligibility; `test_evidence_ingestion.py` covers SEC parsing/provenance and unavailable filings; `test_analysis.py` covers stale exclusion and missing-current disclosure | Capture evidence list, empty/partial evidence, stale item, source link, expanded citation details and safe failure; verify title/type/date/freshness/support span/identifier are readable and links open safely; verify V2 citation IDs expand to equivalent metadata | WP5 Sol (Debate evidence contract); WP6 Terra (Debate presentation); WP7 Terra/Luna (Evidence screen migration) |
| **Examination**: claim selection, loading/result/failure, evidence support and bounded question types | Partial: legacy claim examination is implemented; full end-to-end UI and V2 selection proof are missing | `apps/mobile/src/screens/ExaminationScreen.tsx`, `apps/mobile/src/examinationState.ts`, `apps/mobile/src/explanationView.ts`, `apps/mobile/App.tsx`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/services/analysis.py`, `backend/app/services/guardrails.py` | `examinationState.test.ts` blocks duplicate questions while pending; `test_api.py::test_watchlist_and_analysis_flow` covers legacy analysis flow; `test_analysis.py` covers evidence/context behavior; `test_guardrails.py` covers financial-language rewrite | Select each claim and question type; verify loading disables only the intended controls, success evidence, failure/retry and no Debate mutation; run with missing/partial evidence and check accessible live announcements at 390/1280px | WP6 Terra (V2 Explanation integration); WP7 Luna (legacy screen migration); Root requires an end-to-end examination test |
| **V2 Debate lifecycle**: queued, running, streaming draft, persisted turn, retry delay, failed, cancelled, reconnect, `awaiting_user` | Implemented at state/transport level; screen visual acceptance unverified | `apps/mobile/src/screens/LiveDebateScreen.tsx`, `apps/mobile/src/debateStream.ts`, `apps/mobile/src/liveDebateView.ts`, `apps/mobile/src/debateActionState.ts`, `backend/app/main.py`, `backend/app/services/debate_preview.py`, `backend/app/services/debate_event_broker.py`, `backend/app/services/debate_worker.py`, `backend/app/services/debate_job_state.py` | Mobile `debateStream.test.ts` covers SSE fragmentation, temporary drafts, canonical completion, event/delta gaps, job retry/failure, cancellation, canonical reload and cursor recovery; `liveDebateView.test.ts` covers visible queued/running/retry/cancel/final/challenge states; backend `test_debate_preview_api.py`, `test_debate_streaming_orchestrator.py`, `test_debate_worker.py`, `test_debate_job_state.py`, `test_debate_event_broker.py` cover durable lifecycle, retry, recovery, cancellation and safe errors | Exercise every state in `review_fixture`, including network interruption and cursor expiry; verify drafts look temporary, canonical messages persist, auto-scroll does not interrupt reading, retry/cancel availability matches status, connection recovery is announced and no provider detail leaks | WP2 Terra (fixtures); WP6 Terra (chat surface); Sol reviews queue/data contract |
| **Debate semantics**: six Round 1 Bull/Bear turns, Interim Judge, one durable Challenge, four Round 2 turns, Final Judge, mutual rebuttals and citation constraints | Backend semantics implemented; V2 visual behavior remains unverified while the default local/public path shows the Legacy card sequence | `backend/app/domain/debate.py`, `backend/app/services/debate_orchestrator.py`, `backend/app/providers/deterministic_debate.py`, `backend/app/providers/debate_agents.py`, `apps/mobile/src/screens/LiveDebateScreen.tsx`, `apps/mobile/src/types.ts` | `test_debate_domain.py` checks round/exchange counts and role invariants; `test_debate_orchestrator.py` checks six turns, latest-opponent targeting, Challenge and Final Judge, ordered events and safe failures; `test_debate_preview_api.py` checks preview shape, challenge persistence, ownership and legacy compatibility | Verify chronological chat order: Bull left, Bear right, User Challenge distinct/centred, Interim and Final Judge centred; verify every completed turn visibly separates argument/facts/interpretation/uncertainty and citations expand to dated source metadata; check desktop constrained width and mobile offsets | WP6 Terra (chat presentation); Sol owns semantics/evidence contract; Root owns final transcript acceptance |
| **Explanation**: exact-term selection, loading/result/error, read-only behavior and no Debate state mutation | Implemented, V2 visual integration unverified | `apps/mobile/src/explanationView.ts`, `apps/mobile/src/explanationRequest.ts`, `apps/mobile/src/screens/LiveDebateScreen.tsx`, `backend/app/services/explanation.py`, `backend/app/providers/explanation.py`, `backend/app/providers/groq_explanation.py`, `backend/app/main.py` | `explanationView.test.ts` requires exact complete-message selection and invalidates stale requests; `explanationRequest.test.ts` checks API field contract; `debateActionState.test.ts` distinguishes read-only explaining; `test_explanation_service.py` checks grounding, ownership, evidence bounds, safe provider failure and guardrails; `test_debate_preview_api.py` checks bounded read-only endpoint | Select valid/invalid text, open/close panel during streaming, success/error/retry and provider-disabled state; verify request cannot mutate transcript/session, panel is keyboard reachable and explanation provenance is visible | WP6 Terra (V2 panel); Sol reviews read-only and evidence boundary |
| **History**: legacy analysis, active V2 session, Interim/Final distinction, reopen correct ticker, empty state and load failure | Partial: state helpers and routes exist; native/Web visual and cross-route evidence absent | `apps/mobile/src/screens/HistoryScreen.tsx`, `apps/mobile/src/debateHistoryView.ts`, `apps/mobile/App.tsx`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/services/analysis.py`, `backend/app/repositories/*` | `debateHistoryView.test.ts` distinguishes durable final Judge, interim and active sessions; `test_analysis.py::test_analysis_history_is_isolated_by_user`; `test_debate_preview_api.py` covers owner-scoped reads and persisted sessions; `stockDetail.test.ts` verifies saved Debate ticker loads matching bundle | Verify empty/history load failure, legacy and active V2 rows, interim/final labels, reopening restores ticker and bundle, owner isolation and responsive row actions at 390/1280px | WP7 Luna (history surface migration); Sol reviews persistence/ownership |
| **About and diagnostics**: product guidance, progressive technical disclosure, health status and safe error wording | Partial: screens/disclosures exist; no focused automated or visual characterization | `apps/mobile/src/screens/AboutScreen.tsx`, `apps/mobile/src/screens/LegacyDebateScreen.tsx`, `apps/mobile/src/components/common.tsx`, `apps/mobile/App.tsx`, `backend/app/main.py` health routes | No dedicated About/diagnostic screen test. `test_api.py` covers `/health` and degraded cache health; `webAccessibility.test.ts` covers selected labels/contrast; typecheck/build provide compile evidence | Capture normal About, sign-out, health/degraded status and expanded diagnostic details; verify product guidance precedes implementation detail, provider internals are not primary copy, and safe error text at all required widths | WP7 Luna (content/disclosure); WP3 Terra (shared status styling); Root checks safe wording |
| **Cross-cutting accessibility/responsiveness**: navigation, keyboard focus, screen-reader labels/status, 44px targets, 200% zoom, reduced motion and no horizontal overflow | Partial: token/helper intent and selected tests exist; complete surface coverage is absent | `apps/mobile/App.tsx`, `apps/mobile/src/appShell.ts`, `apps/mobile/src/theme.ts`, `apps/mobile/src/theme/tokens.ts`, `apps/mobile/src/components/common.tsx`, all screen modules | `appShell.test.ts` covers 320/390/768/1280 shell values; `webAccessibility.test.ts` covers required viewport frame, contrast and token target checks; individual stream/auth/evidence tests cover selected accessibility state props | Browser screenshots and keyboard/SR pass at 320/390/768/1280px for every affected screen; verify focus visibility/order, 44px targets, 200% zoom, reduced-motion behavior, chart alternatives and no page-level overflow on native/Web | WP3 Terra (foundation); WP8 Luna (mechanical screen sweep); Root owns device/browser acceptance |
| **Legacy Debate fallback**: labelled fallback and synchronous path remain available until deliberate V2 rollout | Implemented, rollout behavior needs explicit review | `apps/mobile/App.tsx` (`DEBATE_V2_UI_ENABLED`), `apps/mobile/src/screens/LegacyDebateScreen.tsx`, `apps/mobile/src/components/debate/*`, `apps/mobile/src/api.ts`, `backend/app/main.py`, `backend/app/services/analysis.py` | `test_debate_preview_api.py::test_preview_is_hidden_by_default_while_legacy_analysis_still_works`; `test_debate_preview_api.py::test_enabled_preview_does_not_change_legacy_analysis_contract`; `test_analysis.py` validates legacy Bull/Bear/evidence/trace paths | Run with V2 flag off/on; verify labelled fallback, synchronous run, error/retry, evidence and examination remain usable; verify flag cannot silently replace live production data or bypass coverage boundaries | WP6 Terra (shared presentation rollout); Root owns release gate and rollback check |

## WP0 automated and browser characterization

The following commands passed on 2026-09-07 against baseline revision
`898e821`, using credential-free deterministic test or demo paths:

```sh
cd apps/mobile
npm run test:stream  # 36 passed
npm run typecheck
npm run build:web

cd ../../backend
.venv/bin/pytest -q  # 345 passed, 1 existing Starlette/httpx warning
```

Root also ran the current Expo Web application against the local FastAPI demo
backend and inspected representative 390 px and 1280 px layouts. The Watchlist
loaded meaningful content without a browser error overlay or console warning.
At 1280 px the document had no horizontal overflow. The AAPL workspace showed a
quote but explicitly hid the curve and paused RSI/MACD because daily history was
not verified. The Legacy Debate rendered a vertical sequence of full-width
Snapshot, Judge, Bull, and Bear cards rather than the accepted chat pattern.

The demo-mode AAPL quote was labelled as a Finnhub quote with a 2026-09-04 time,
while its subsequently generated Legacy Debate used a 2026-02-25 close and a
different price. These values are characterization evidence of the current
ambiguous fallback/provenance presentation, not a claim about live market data.
Screenshots were visually inspected and deliberately not committed; they
contained no credentials or private user content.

## Remaining evidence gaps after WP0

The matrix maps every preservation-contract row to at least one implementation
surface and a proposed regression target. The following are not yet sufficient
as WP0 completion evidence and therefore remain open rather than being marked
done:

- Representative 390/1280 warm-theme Web characterization is recorded, but the
  complete 320/390/768/1280 redesigned-state matrix, native simulators, and a
  physical device remain later acceptance gates.
- No deterministic `review_fixture` currently covers all chart, freshness,
  partial-history, unavailable, and V2 lifecycle states. Existing
  `demo_fallback` is not evidence of a safe review fixture.
- WP1 has now normalized and mirrored frontend/backend RSI, MACD, moving-average,
  and volatility rules. Visual comparison of the resulting series remains a
  WP4 acceptance task.
- Existing mobile tests are logic/state tests; they do not prove that the
  current warm-paper screens meet the Prototype's dark visual direction.
- There is no dedicated end-to-end UI test for authentication, examination,
  About/diagnostics, complete macro-series coverage, or the V2 facts/citation
  presentation contract.
- Deployment parity is not part of this local matrix: public/demo verification
  still needs a same-SHA staging run as required by the acceptance matrix.

## WP0 completion checklist

- [x] Every row above has a reproducible local command or fixture for its
  automated evidence.
- [x] Representative screenshots were captured and their observations and
  viewport metadata were appended to
  [`phase-8-verification-record.md`](phase-8-verification-record.md), clearly
  labelled as characterization evidence rather than design approval.
- [x] No test helper or production behavior was added or changed during WP0.
- [x] Root review confirms no preservation row is silently dropped before WP1,
  WP2, or WP3 starts.
