# History

## Project origin

ColaDong began as `Dong`, a shared friend-group ledger. The project owner is
a backend developer with some Django experience, currently an MSc student in
AI and robotics. The original frontend (six templates plus the shared
stylesheet) was written by Claude and handed over with `README_UI.md` as the
context-variable contract, so the frontend and backend could be built
independently. The owner then built the backend — models, views, forms,
services, tests — with AI-agent help. The project later grew into a
three-app platform: `Dong`, `Ejlas`, and `ipcalc`.

As of the last docs update, all three apps worked, the test suite was green
with 63 tests, and deployment scripts lived in `deploy/`. Check the actual
repo state before trusting that summary.

## Documentation history

- `README.md` covers what the project is and how to run it.
- `BACKEND_GUIDE.md` covers how the backend was built.
- `Decisions.md` was the implementation decision log.
- `AgentStartHere.md` was the restored session-start onboarding file.
- `CONTEXT.md` became the rich project-context file and is now being split
  into `agent/` files.
- Docs were made consistent with the implemented backend; 63 tests pass.
- Deleted planning files were restored, then this restructuring began.

## Commit history (old → new)

- `07f31db` — settings cleanup: absolute template dir, auth redirect,
  dropped stray `MAILERS`, pinned Django 6.1.
- `6f6bc0d` — models and `0001_initial` migration.
- `e5dddcb` — admin registration for both `Dong` models.
- `bb3fb8a` — login/logout wiring, trailing-slash URLs, root redirect.
- `b707b8c` — view layer: `services.py`, `forms.py`, `views.py`,
  `tests.py`; 18 tests green.
- `da62601` — `RETURN.txt` sync flag file.
- `cb76ef4` — fixed form-error flattening, declared `PaymentForm.amount`
  explicitly, added add-record/records-filter tests; 27 tests green.
- `3562470` — `Decisions.md` and `README.md` rewrite.
- `7684ddd` — refreshed `AgentStartHere.md` after doc commits.
- `f85d4c8` — set `pyproject.toml` description.
- `ae2927f` — owner note.
- `816825f` — features pass: GET filtering, pagination, CSV export,
  borrowed-money direction toggle, settle-up suggestions, monthly stats.
- `0630429` — IP-address logging and removed `AUTH_PASSWORD_VALIDATORS`;
  this commit introduced a group-buy split regression.
- `4e824c9` — fixed group-buy payer exclusion, extracted `apply_filters()`,
  dropped unused `user` arg from `settle_up()`, added group-purchase badge,
  borrowed-money dynamic label, IP in admin/CSV, CSS hairline fix, 13 new
  tests (54 total).
- Deployment — `deploy/install.sh`, `deploy/update.sh`, `AdminUpdateView`,
  admin “Update now” button, `gunicorn~=23.0`, env-var-aware settings.
- Multi-app restructure — `dong:` namespace, project `urls.py` reorganized,
  homepage at `/`, `base.html` `app_nav` block, `LOGIN_REDIRECT_URL` → `/`.
- `Ejlas` app — `Meeting` model, week board, add-meeting view, conflict
  services, 9 tests.
- `ipcalc` app — stateless client-side subnet calculator.

## Doc discrepancy resolved

- `AgentStartHere.md` said `TIME_ZONE = "Etc/UTC+3:30"`, but
  `ColaDong/ColaDong/settings.py:110` sets `TIME_ZONE = 'UTC'`. The agent
  notes use `UTC` as the current fact.

## Multi-app plan (old `PLAN.md`)

The original `PLAN.md` at repo root described the multi-app restructuring
and the two new apps. All items were executed: restructuring, Ejlas, and
IP Calculator are implemented and committed. Design decisions from that
plan are preserved in `agent/DECISIONS.md` under "Multi-app restructure."
The file is deleted after this restructuring.

## Current restructuring

- Root `CONTEXT.md` will become a tiny auto-load hook.
- Rich domain facts move to `agent/DOMAIN.md`.
- Decisions move to `agent/DECISIONS.md`.
- Active plan moves to `agent/PLAN.md`.
- Future work moves to `agent/BACKLOG.md`.
- History and completed work move to `agent/HISTORY.md`.
- `agent/` is the working-memory directory, separate from project code.
