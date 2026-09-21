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

Then open http://127.0.0.1:8000/ — the homepage lists all apps. Log in,
then pick an app:

- `/dong/` — Balances (default)
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
ColaDong/                  project package (settings, urls)
ColaDong/Dong/             shared ledger app
  models.py                Payment, GroupPurchase
  services.py              compute_balances, split_amount, settle_up, monthly_stats
  forms.py                 PaymentForm, RecordFilterForm, GroupBuyForm
  views.py                 Balances, AddRecord, Records, RecordsCsv, GroupBuy
  tests.py                 54 tests
  admin.py
ColaDong/Ejlas/            meeting planner app
  models.py                Meeting
  services.py              times_overlap, find_conflicts, find_week_conflicts
  forms.py                 MeetingForm
  views.py                 WeekBoardView, AddMeetingView
  tests.py                 9 tests
  admin.py
ColaDong/ipcalc/           subnet calculator (stateless, client-side JS)
  views.py                 CalculatorView
ColaDong/templates/        shared + per-app templates, all extend base.html
ColaDong/static/css/coladong.css    the whole design system
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

- **`CONTEXT.md`** — why the project is shaped the way it is: the domain
  rules, the visual language, the trust model, deferred scope.
- **`BACKEND_GUIDE.md`** — a teaching walkthrough of how each piece of the
  backend works (constraints, CBVs, aggregation, transactions, the
  largest-remainder rounding algorithm).
- **`README_UI.md`** — the frontend handoff contract: exactly which context
  variables and POST fields each template expects.
- **`Decisions.md`** — implementation decisions made while building the
  backend, and the reasoning behind each.
- **`AgentStartHere.md`** — cold-start handoff for AI agents: environment
  specifics, conventions, the `RETURN.txt` sync flag protocol.
