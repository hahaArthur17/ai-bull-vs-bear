# Weekly Reports

Weekly reports are the append-only project memory. Keep the roadmap short and
put implementation detail, verification evidence, blockers, and handoff notes
in one report per project week.

## Context recovery order

When resuming the project:

1. read `../weekly-roadmap.md` for the current status;
2. read the [project issue log](../issue-log.md) for unresolved risks and
   prior incident evidence;
3. read the latest report in this folder;
4. read the active operating checklist, currently `../week-4-todo.md`;
5. open only the architecture/setup documents linked by the latest report; and
6. compare the repository state with the GitHub Project before choosing work.

## Reports

- [`project-week-04.md`](project-week-04.md) — authentication, persistence,
  live evidence, vector retrieval, and live-price cache implementation.
- [`project-week-05.md`](project-week-05.md) — vectorization research,
  multi-profile storage, source-aware chunking, XBRL facts, and release checks.
- [`project-week-06.md`](project-week-06.md) — current-price Debate integrity,
  interactive charts, and the first cached macro-market context layer.

## Template for a new report

- goal and dates;
- completed work with commit IDs;
- live state and verification commands/results;
- decisions and why they were made;
- unfinished work, exact blocker, and required owner action;
- recommended next three tasks; and
- links to changed architecture/setup documents.

Never include passwords, API keys, JWTs, service-role keys, private email
addresses, or screenshots containing credentials.
