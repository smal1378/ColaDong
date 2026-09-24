# Agent Index

## Session start

Read root `CONTEXT.md`, then this file, then `agent/PLAN.md`. Load other
files only when the task needs them.

## File map

| File | Purpose |
| --- | --- |
| `CONTEXT.md` | Tiny auto-loaded hook. Hard rules + pointer here. |
| `agent/INDEX.md` | Map, environment, commands, hard rules. |
| `agent/STRATEGY.md` | How this memory system works. |
| `agent/DOMAIN.md` | Domain facts and conventions. |
| `agent/PLAN.md` | Active work only. |
| `agent/BACKLOG.md` | Known future work. |
| `agent/DECISIONS.md` | Decisions and rationale. |
| `agent/HISTORY.md` | Completed work and history. |
| `README.md` | Human-facing project overview. |
| `README_UI.md` | Template context-variable contract. |
| `BACKEND_GUIDE.md` | Backend teaching walkthrough. |

## Project identity

ColaDong is a three-app Django platform for a friend group:

- `Dong` — shared lending ledger and group purchases.
- `Ejlas` — weekly meeting board with conflict warnings.
- `ipcalc` — client-side subnet calculator.

One Django project, one theme, one auth session.

## Environment

- Package manager: `uv`
- Python: ≥ 3.13
- Django: 6.1.1, pinned in `pyproject.toml`
- Dev machine: Windows / PowerShell 5.1
- Deploy target: Ubuntu 22.04
- Timezone: `UTC`
- `CheckConstraint` must use `condition=`; the old `check=` keyword was
  removed in Django 6.0 and fails import.
- `SECURE_CSP` is not enabled. If enabled, move the inline script in
  `group_buy.html` into a static JS file.
- The dev laptop may sleep and its clock may jump; don't trust wall-clock
  time as a duration signal. Work in small steps.

## Commands

Run from the repo root:

```powershell
uv sync
```

Run from `ColaDong/`:

```powershell
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py test
```

Test count: 63 tests (54 Dong + 9 Ejlas). `ipcalc` has no server-side
test logic.

## Repo layout

```text
CONTEXT.md
README.md
README_UI.md
BACKEND_GUIDE.md
pyproject.toml
agent/
deploy/
ColaDong/
  manage.py
  ColaDong/
    settings.py
    urls.py
    templates/
  Dong/
  Ejlas/
  ipcalc/
```

Known important paths:

- `ColaDong/manage.py`
- `ColaDong/ColaDong/settings.py`
- `ColaDong/ColaDong/urls.py`
- `ColaDong/ColaDong/templates/`
- `ColaDong/Dong/models.py`
- `ColaDong/Dong/forms.py`
- `ColaDong/Dong/views.py`
- `ColaDong/Dong/services.py`
- `ColaDong/Dong/admin.py`
- `ColaDong/Dong/tests.py`
- `ColaDong/Dong/urls.py`
- `ColaDong/Dong/static/css/coladong.css`
- `ColaDong/Ejlas/models.py`
- `ColaDong/Ejlas/forms.py`
- `ColaDong/Ejlas/views.py`
- `ColaDong/Ejlas/services.py`
- `ColaDong/Ejlas/tests.py`
- `ColaDong/Ejlas/urls.py`
- `ColaDong/ipcalc/views.py`
- `ColaDong/ipcalc/urls.py`

## Hard rules

- Never read `sender` from client input in the `paid` direction.
- Keep frontend and backend group-buy rounding in lockstep.
- Use `CheckConstraint(condition=...)`, not the removed `check=` keyword.
- No code comments unless asked.
- Use project-root-relative paths in docs.
- Do not commit unless explicitly asked.
- Small git commits per logical step; imperative message style, no emoji.
- Keep code simple, clean, and elegant; prefer plain Django patterns.

## URL names

- `home`, `login`, `logout`
- `dong:balances`
- `dong:records`
- `dong:add_record`
- `dong:group_buy`
- `dong:records_csv`

## Template context quick reference

- `records`: `users`, `page` (25/page), `query_string`, `filters`
  (`sender`, `receiver`, `date_from`, `date_to`), `total_amount`.
- `balances`: `balances`, `net_balance`, `settle_up`, `monthly`.
- `add_record`: `form` (refill dict), `error`; POST fields `direction`,
  `receiver` (username string), `amount`, `date`, `note`.
- `group_buy`: `users` (username/name/selected/weight), `form`, `today`,
  `error`; POST fields `payer`, `amount`, `date`, `note`, repeated
  `participants`, and `weight_<username>` per participant.
- `login`: standard auth context plus a flat `error` string.
