# Agent Strategy

This file explains how future agents should use this memory system, and how
to improve it without losing track.

## Purpose

Keep the working set small and recoverable. The root `CONTEXT.md` is the
only file the harness auto-loads. Everything else is loaded only when
relevant.

## File roles

- `INDEX.md` — map, environment, commands, hard rules, session protocol.
- `STRATEGY.md` — this file; how the memory system works.
- `DOMAIN.md` — domain facts that are easy to get backwards.
- `PLAN.md` — active work only.
- `BACKLOG.md` — known future work, one line per item.
- `DECISIONS.md` — decisions and why they were made.
- `HISTORY.md` — completed work and project history.

## Session protocol

1. Read root `CONTEXT.md`.
2. Read `agent/INDEX.md`.
3. Read `agent/PLAN.md`.
4. Read only the topic files needed for the current task.
5. Before finishing, update `agent/PLAN.md` and any file whose durable
   facts changed.

## Loop-safe protocol

When source docs are large or context is near its limit:

1. Write down what is already known in the `agent/` files.
2. Read one source file at a time.
3. Convert that file into the appropriate `agent/` file(s).
4. Check paths, references, and hard rules for that file.
5. Only then move to the next source file.

Never try to load all docs at once. Externalize state as soon as it is
known.

## Rules

- Use project-root-relative paths only. No absolute host paths.
- Keep each file small; split a file when it becomes a grab bag.
- Prefer one owner per fact. If a fact belongs in two places, link to the
  owner instead of duplicating it.
- Update `agent/INDEX.md` whenever the file map changes.
- Keep hard rules visible in root `CONTEXT.md` and `agent/INDEX.md`.
- Do not commit unless explicitly asked.

## Improvement protocol

When improving this strategy:

1. Read `STRATEGY.md`, `INDEX.md`, and `PLAN.md`.
2. Load only the files relevant to the improvement.
3. Make the change.
4. Update `INDEX.md` if the file map changed.
5. Update `HISTORY.md` with a short entry if the change is durable.
