# Planning Documentation

This directory separates current project truth from historical records. Do not
use an old weekly checklist to choose new work.

## Current handoff (2026-10-17)

Core implementation is in final verification/documentation. The owner reports
simulator functionality working; physical-device testing has not been performed.
The later AAPL V2 Session is completed, not waiting for Round 2. Start with the
current resume checklist/status; older saved-session commands, test counts and
App Store compatibility statements are historical. The latest verification
record separates rerun checks, audit findings and remaining release gates.

## Resume here

When resuming development:

1. for the current Expo V2 beta, read
   [`v2-beta-resume-checklist.md`](v2-beta-resume-checklist.md) first;
2. read [`current-status.md`](current-status.md) for the verified baseline and
   known gaps;
3. read the active
   [`portfolio-implementation-plan.md`](portfolio-implementation-plan.md) and
   select only its current phase;
4. read the active phase-specific remediation register, when present;
5. review the [project issue log](issue-log.md) for unresolved or recurring
   risks;
6. read the latest entry in [`reports/`](reports/README.md) when historical
   implementation detail is needed;
7. open only the architecture, API, database, agent, or setup document relevant
   to the selected task; and
8. compare documentation with the repository and tests before changing code.

The repository and passing verification checks are the implementation source
of truth. Planning documents describe intent and must be updated when an
accepted design or completion state changes.

## Active documents

| Document | Purpose |
| --- | --- |
| [`current-status.md`](current-status.md) | Concise, verified current state and limitations. |
| [`v2-beta-resume-checklist.md`](v2-beta-resume-checklist.md) | Exact local V2 beta restart commands, current manual-test state, and ordered next checks. |
| [`portfolio-implementation-plan.md`](portfolio-implementation-plan.md) | Canonical architecture, phases, acceptance tests, and next coding task. |
| [`phase-8-ui-acceptance-matrix.md`](phase-8-ui-acceptance-matrix.md) | Required visual, responsive, accessibility, and device-review evidence for the active UI redesign. |
| [`phase-8-design-remediation.md`](phase-8-design-remediation.md) | Active Phase 8 remediation register for the Prototype dark theme, chart/Debate UX, review fixtures, data integrity, existing-backend release checks, and device acceptance. |
| [`phase-8-preservation-matrix.md`](phase-8-preservation-matrix.md) | WP0 map of existing functions and states to implementation, automated evidence, missing manual proof, and later work-package ownership. |
| [`phase-8-indicator-contract.md`](phase-8-indicator-contract.md) | WP1 canonical daily-history, sufficiency, formula, provenance, and refresh-success rules. |
| [`issue-log.md`](issue-log.md) | Append-only material incidents and remediation evidence. |
| [`reports/`](reports/README.md) | Append-only weekly implementation and verification history. |

Superseded plans and original MVP notes are preserved under
[`archive/`](archive/README.md) and must not be used as the active backlog.

## Working rules

- Keep one canonical implementation plan instead of starting new week-numbered
  todo files.
- Make one focused commit per small, independently reviewable change.
- Update acceptance criteria in the active plan in the same change that proves
  them complete.
- Add a dated report for a substantial milestone, production incident, or
  handoff; do not copy the full current plan into a report.
- Never include credentials, JWTs, personal passwords, private email addresses,
  or screenshots containing secrets.
- Preserve completed historical records, but label or archive them so they
  cannot be mistaken for current instructions.
