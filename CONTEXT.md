# Cola Dong — agent context

This file is auto-loaded by the agent harness. It contains only the hard
rules and a pointer to the full working-memory set.

## Hard rules

- Never read `sender` from client input in `add_record`.
- Keep frontend and backend group-buy rounding in lockstep (largest-remainder).
- Use `CheckConstraint(condition=...)`, not the removed `check=` keyword.
- No code comments unless asked.
- Do not commit unless explicitly asked.
- Amounts are whole-dollar integers ($1–$999,999), never floats.
- Balance sign: positive = they owe you, negative = you owe them.
- The double rule (`border: 3px double`) marks finalized totals only —
  never reuse it as generic decoration.

## Working memory

Read `agent/INDEX.md` for the full set: domain rules, decisions, history,
active plan, deferred work, and the loop-safe protocol.

## Environment

- `uv` package manager, Python ≥ 3.13, Django 6.1.1
- Run commands from `ColaDong/` subdir: `uv run python manage.py ...`
- Tests: `uv run python manage.py test` (63 tests)
