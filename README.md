# Cola Dong

A private shared ledger for a friend group, built with Django.

- Note: I've (Esmail) created this project using AI Agents to try it out, and also may use the project.

If Alice pays Bob $100, it's recorded, and Bob now owes Alice $100. If Bob
then pays Carl $100, Carl owes Bob instead. The app tracks who owes whom
what, shows each person's running balance, and can split a group purchase
across several people (with weighted shares) in one click.

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

Then open http://127.0.0.1:8000/ and log in.

## Tests

```bash
cd ColaDong
uv run python manage.py test Dong
```

## Layout

```
ColaDong/                  project package (settings, urls)
ColaDong/Dong/             the app
  models.py                Payment, GroupPurchase
  services.py              compute_balances, split_amount
  forms.py                 PaymentForm, RecordFilterForm, GroupBuyForm
  views.py                 the six views
  tests.py                 27 tests
  admin.py
templates/                 six pages, all extend base.html
static/css/coladong.css    the whole design system
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
