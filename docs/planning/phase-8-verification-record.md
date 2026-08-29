# Phase 8 verification record

**Status:** Partial evidence recorded; Phase 8 remains in progress  
**Recorded:** 2026-08-30  
**Subject revision:** `58c3c53` (`test: verify responsive and accessible web flows`)

This is an honest acceptance record, not a release sign-off. It uses only the
deterministic demo backend and `EXPO_PUBLIC_AUTH_MODE=demo`; no credentials,
external market calls, or model calls were used.

## Automated baseline

From `apps/mobile`, the following passed at the subject revision:

```sh
npm run test:stream  # 35 passing tests
npm run typecheck
npm run build:web
```

The Web export built successfully. The focused tests cover all required CSS
widths, navigation target fit, focus-ring token strength, and the Watchlist
label contrast regression fixed in the subject revision.

## Web browser verification

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
initial axe audit had 0 violations.

## Simulator review

| Target | Result | Executed flow | Limitation |
| --- | --- | --- | --- |
| Android Emulator — Pixel (`emulator-5556`, `sdk_gphone16k_arm64`) | Partial pass | Chrome opened the local deterministic Web bundle through `10.0.2.2`; catalog/watchlist data loaded, source/freshness wording remained visible, and direct taps reached About and the empty History. Android's accessibility tree exposed all four bottom-navigation labels and the About disclosure. | This is Android Chrome running the Expo Web bundle, not the native Expo Go/standalone app. Expo Go was not installed because the required SDK 52 APK download is 211 MB and did not make transfer progress in the available verification window. Chrome's own Translate prompt appeared once and was not treated as application UI. |
| iOS Simulator — iPhone 17 Pro, iOS 26.5 | Blocked | Simulator booted and Safari was sent the local Web URL. | Safari's first-run Start Page onboarding obscured the app, and the available iOS automation provider did not return within 30 seconds. No app-page result is claimed. |
| Physical device | Not run | No physical iOS or Android device was connected to the workstation. | Required before Phase 8 can close. A device must be unlocked, developer/USB-debugging enabled where applicable, and able to reach the local backend through the workstation LAN address (not `10.0.2.2`). |

Android screenshots were visually inspected after data loaded and after About and
History navigation. They showed a single-column layout, a persistent bottom
navigation bar, visible source/freshness wording, and no application error
banner in the successful demo run.

## Remaining closure gates

- Run the actual managed Expo app or a standalone/dev build on both iOS and
  Android simulators; a browser bundle is supporting evidence only.
- Run the representative flow on at least one physical device and record its
  OS/device, commit, screenshot, flow, and result.
- Exercise the remaining state-gated V2 Debate views in a visual device pass
  while preserving default-off V2/Groq Explanation, read-only Explanation,
  `catalog_only` zero-call behavior, provenance, and `awaiting_user`-only
  Challenge.
- Run the complete backend suite and all Phase 8 acceptance checks before
  changing Phase 8 to Done.
