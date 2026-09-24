# Cola Dong

A multi-app platform for a friend group, built with Django.

- Note: I've (Esmail) created this project using AI Agents to try it out, and also may use the project.

Three apps, one shared theme:

- **Dong** — a shared ledger. If Alice pays Bob $100, Bob owes Alice $100.
  Tracks balances, records payments, and splits group purchases (weighted
  shares) in one click.
- **Ejlas** — a weekly meeting board (Saturday–Thursday, Iran calendar).
  Add meetings, pick attendees, and get conflict warnings when two meetings
  overlap in time for the same person or the same place.
- **IP Calculator** — a stateless subnet calculator. Enter a CIDR or
  network + prefix; get network address, broadcast, usable hosts, mask,
  and classification (private/reserved/public).

- Whole-dollar amounts only ($1–$999,999), stored as integers
- Signed balances: positive = they owe you, negative = you owe them
- Server-rendered Django templates, no JavaScript framework
- Django 6.1, Python ≥ 3.13, environment managed by [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync                    # from this directory
cd ColaDong
uv run python manage.py migrate
uv run python manage.py createsuperuser   # or add Users in /admin
```

## Run

```bash
cd ColaDong
uv run python manage.py runserver
```

Then open http://127.0.0.1:8000/ — log in, and the homepage lists all
apps. Each app is namespaced under its own path:

- `/dong/` — Balances (default after add-record/group-buy)
- `/ejlas/` — Week board
- `/ip/` — IP Calculator

## Tests

```bash
cd ColaDong
uv run python manage.py test
```

63 tests total (54 Dong + 9 Ejlas). The IP Calculator is client-side JS
with no server-side logic to test.

## Layout

```
ColaDong/                  repo root (git lives here)
  ColaDong/                Django project dir (manage.py is here)
    ColaDong/              settings, project urls, wsgi/asgi
    Dong/                  shared ledger app
      models.py            Payment, GroupPurchase
      services.py          compute_balances, split_amount, settle_up, monthly_stats
      forms.py             PaymentForm, RecordFilterForm, GroupBuyForm
      views.py             Balances, AddRecord, Records, RecordsCsv, GroupBuy
      tests.py             54 tests
      static/css/          coladong.css — the shared design system (all apps)
    Ejlas/                 meeting planner app
      models.py            Meeting
      services.py          times_overlap, find_conflicts, find_week_conflicts
      forms.py             MeetingForm
      views.py             WeekBoardView, AddMeetingView
      tests.py             9 tests
    ipcalc/                subnet calculator (stateless, client-side JS)
      views.py             CalculatorView
    templates/             base, home, login + per-app templates (balances,
                           records, add_record, group_buy, ejlas/, ipcalc/)
   deploy/                  install.sh, update.sh (Ubuntu 22.04)
   CONTEXT.md               agent auto-load hook (hard rules + pointer)
   README_UI.md             frontend handoff contract (context variables)
   BACKEND_GUIDE.md         teaching walkthrough of the Dong backend
   agent/                   agent working memory (domain, decisions, plan, etc.)
```

## Deploy (Ubuntu 22.04)

```bash
sudo bash deploy/install.sh
```

The script creates a non-root service user, installs `uv`, writes the
systemd unit (gunicorn on `127.0.0.1:8000`, `Restart=always`), and
generates an nginx example config. After install, update with:

```bash
bash deploy/update.sh
```

or click **"Update now"** on the Django admin dashboard (superuser
only). Both paths are root-free: the script kills gunicorn via its PID
file and systemd restarts it.

## Docs

- **`CONTEXT.md`** — agent auto-load hook: hard rules and a pointer to
  `agent/INDEX.md` for the full working-memory set.
- **`README_UI.md`** — the frontend handoff contract: exactly which context
  variables and POST/GET field names each template expects.
- **`BACKEND_GUIDE.md`** — a teaching walkthrough of how the Dong backend
  was built (constraints, CBVs, aggregation, transactions, the
  largest-remainder rounding algorithm).
- **`agent/`** — agent working memory: domain rules (`DOMAIN.md`),
  implementation decisions (`DECISIONS.md`), history (`HISTORY.md`),
  active plan (`PLAN.md`), deferred work (`BACKLOG.md`), and the
  loop-safe protocol (`STRATEGY.md`).
