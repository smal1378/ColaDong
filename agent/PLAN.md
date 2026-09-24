# Active Plan

## Task

Restructure documentation into the persistent `agent/` memory system.

## Completed

- Created `agent/`.
- Wrote initial `agent/` files from already-known context.
- Processed `CONTEXT.md` into `agent/DOMAIN.md`, `agent/INDEX.md`,
  `agent/HISTORY.md`, and `agent/BACKLOG.md`.
- Processed `Decisions.md` into `agent/DECISIONS.md`.
- Processed `AgentStartHere.md` into `agent/INDEX.md`, `agent/DOMAIN.md`,
  `agent/HISTORY.md`, and `agent/DECISIONS.md`.
- Processed old `PLAN.md` (multi-app restructuring plan); all content
  historical and preserved in `agent/HISTORY.md` and `agent/DECISIONS.md`.

## Next

1. Update `README.md` and `BACKEND_GUIDE.md` cross-references; verify.
2. Rewrite root `CONTEXT.md` as the tiny auto-load hook; verify.
3. Delete root `AgentStartHere.md`, `PLAN.md`, and `Decisions.md` only
   after their content is preserved in `agent/`.
4. Run tests and grep for absolute paths/stale references.

## Working rules

- One source file at a time.
- After each conversion, check that the new file obeys the rules in
  `agent/STRATEGY.md`.
- Keep the active plan short; move finished items to `agent/HISTORY.md`.
