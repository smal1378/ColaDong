# AgentStartHere — Cola Dong repo handoff

Read this first if you're a new agent (or human) picking up this repo.
`CONTEXT.md` explains *why things are shaped this way*; this file explains
*where things are right now, what's done, and what's left*.

---

## 1. What the project is

Cola Dong is a weekend Django web app: a shared ledger for a friend group.
Each friend has a plain Django `User` account. The core mechanic:

> If I pay you $100 today, it gets recorded, and then **you owe me $100**.
> If you then give someone else $100, they owe you $100 instead.

Plus one extension: **group purchases** — one person (the payer) pays a
total, and several other people each owe a share.

This is a *lending* ledger, not a Splitwise-style expense splitter.
**Get the direction backwards and every balance in the app flips sign.**
Recording a payment by Alice to Bob creates a row where
`sender=Alice, receiver=Bob`; from Bob's viewpoint Bob now owes Alice.

## 2. Ownership and division of labor

- The repo owner is a backend developer deliberately writing the Django
  backend themselves to learn Django. An AI agent (this project's
  overnight collaborator) has been helping implement the backend.
- The frontend (6 templates in `ColaDong/templates/` +
  `static/css/coladong.css`) was written by Claude and is **complete**.
  Treat the templates as a fixed contract.
- `README.md` (project overview + setup), `README_UI.md` (the frontend
  handoff contract) and `BACKEND_GUIDE.md` (a teaching walkthrough,
  deliberately stops short of finished code) document the plan.
- The visual language: greenbar accounting sheet — pale alternating rows,
  hairline rules, right-aligned monospaced figures, `3px double` rules only
  where something totals up. Debts render red in parentheses
  (`($80.00)`); amounts owed to you render plain. Design tokens live in
  the `:root` block at the top of `static/css/coladong.css`.

## 3. Environment

- Windows machine, PowerShell 5.1 shell.
- Package management: **`uv`** (not pip/venv). `uv sync` to install.
- Django **~=6.1** (pinned in `pyproject.toml`). Python ≥3.13.
- Timezone is UTC+03:30 (`TIME_ZONE = "Etc/UTC+3:30"` in settings).
- The laptop **goes to sleep** and the clock jumps; never trust wall-clock
  time as a planning signal. Work in small committed steps.
- Common commands (run from the `ColaDong/` subdir, which holds
  `manage.py`):
  - `uv run python manage.py runserver`
  - `uv run python manage.py test` (all apps, 63 tests)
  - `uv run python manage.py makemigrations` / `migrate`

### Django 6.x trap (already stepped on)
`CheckConstraint(check=...)` was removed in Django 6.0 — it must be
`CheckConstraint(condition=...)`. `models.py` uses `condition=`.

## 4. Repo layout

```
ColaDong/                     <- repo root (git lives here)
  ColaDong/                   <- Django project dir (manage.py is here)
    ColaDong/                 <- settings/urls (project-level: home, login, includes)
    Dong/                     <- shared ledger app (app_name="dong")
      models.py               Payment, GroupPurchase
      views.py                Balances, AddRecord, Records, RecordsCsv, GroupBuy
      forms.py                PaymentForm, RecordFilterForm, GroupBuyForm
      services.py             compute_balances(), split_amount(), settle_up(),
                              monthly_stats()
      admin.py                both models registered
      tests.py                54 tests
      urls.py                 app_name="dong", 5 patterns
      migrations/             0001_initial, 0002_payment_ip_address
    Ejlas/                    <- meeting planner app (app_name="ejlas")
      models.py               Meeting (start_time, end_time, place, attendees)
      views.py                WeekBoardView, AddMeetingView
      forms.py                MeetingForm
      services.py             times_overlap(), find_conflicts(), find_week_conflicts()
      admin.py                MeetingAdmin
      tests.py                9 tests
      urls.py                 app_name="ejlas", 2 patterns
      migrations/0001_initial.py
    ipcalc/                   <- subnet calculator (app_name="ipcalc", stateless)
      views.py                CalculatorView (serves template, all logic in JS)
      urls.py                 app_name="ipcalc", 1 pattern
    templates/                base, home, login, balances, add_record,
                              records, group_buy, ejlas/ (2), ipcalc/ (1)
    static/css/coladong.css   shared design system (all apps)
  CONTEXT.md                  why things are shaped this way
  BACKEND_GUIDE.md            original build walkthrough
  README_UI.md                frontend handoff contract
  Decisions.md                implementation decision log
  PLAN.md                     restructure + new apps plan
  RETURN.txt                  sync flag (see §8)
  AgentStartHere.md           <- you are here
```

## 5. Domain rules (enforced in code)

- **Amounts**: whole-dollar integers, 1–999999. `PositiveIntegerField`
  with `MinValueValidator(1)` / `MaxValueValidator(999_999)` — no cents,
  true by construction. Never switch to `DecimalField`.
- **Balance sign convention**: one signed integer per (viewer, other):
  **positive = the other person owes you; negative = you owe them.**
  Implemented in `services.compute_balances(user)` with two
  `values().annotate(Sum(...))` queries (one for payments out, one for
  payments in), merged into per-user dicts `{username, name, balance}`.
- **`sender != receiver`** enforced twice: `PaymentForm.clean_receiver`
  and a DB `CheckConstraint` (belt to suspenders).
- **Trust boundaries**:
  - `add_record`: sender is *never* read from POST. The form posts
    `receiver` as a **username string**; `PaymentForm` uses
    `to_field_name="username"` and `AddRecordView.get_form_kwargs`
    restricts the queryset to exclude the logged-in user; the view sets
    `form.instance.sender = request.user`.
  - `group_buy`: the *payer* IS selectable and may be another user —
    deliberate (a friend can log a purchase on someone's behalf; small
    group, honor system).
- **Rounding**: largest-remainder method. `services.split_amount(total,
  weights)` is a direct Python port of the JS preview in
  `group_buy.html` — both must always agree, or the preview and the
  saved rows diverge. Floor each exact share, hand leftover dollars one
  at a time to the largest fractional parts.
- **Group-buy share rows**: the payer gets no share row for themselves
  (a self-payment row is skipped), and the whole save — GroupPurchase +
  all Payment rows — happens inside `transaction.atomic`.

## 6. Template context contract (backend must feed these exactly)

Templates expect **plain dicts, not form instances** for refill-after-error
(`forms.refill_dict(form)` converts: bound value or field initial;
errors as `;`-joined string).

| Page (url name) | Context variables |
|---|---|
| `records` | `users` (all User objects), `page` (Django Page object, 25/page), `query_string` (current filter params minus `page`, for pagination links), `filters` (dict with sender/receiver/date_from/date_to), `total_amount` (int Sum of shown amounts) |
| `balances` | `balances` (list of dicts: username, name, balance), `net_balance` (int), `settle_up` (list of {from,to,amount} dicts), `monthly` (list of {month, sent, received, sent_count, received_count} dicts) |
| `add_record` | `form` (refill dict), `error` (string, rendered by base.html) |
| `group_buy` | `users` (list of dicts: username, name, selected, weight), `form` (refill dict: payer/amount/date/note), `today` (YYYY-MM-DD string), `error` |
| `login` | standard auth context + flat `error` string |

Field names:
- `add_record` (POST): `receiver` (username string), `amount`, `date`, `note`
- `records` filter (**GET** form, so filtered URLs are bookmarkable):
  `sender`, `receiver`, `date_from`, `date_to`; pagination via `page`
- `group_buy` (POST): `payer` (username), `amount`, `date`, `note`,
  `participants` (repeated usernames), `weight_<username>` per participant

## 7. Implementation status

### Done and committed (git log, old → new)
1. `07f31db` settings cleanup: absolute template dir, auth redirect
   settings, dropped stray `MAILERS`, pinned Django 6.1
2. `6f6bc0d` models + `0001_initial` migration, applied
3. `e5dddcb` admin registration for both models
4. `bb3fb8a` login/logout wiring, trailing-slash URLs, root redirect
5. `b707b8c` the whole view layer: `services.py`, `forms.py`,
   `views.py` (BalancesView, AddRecordView, RecordsView, GroupBuyView),
   `tests.py` — test suite green at commit time (18 tests)
6. `da62601` `RETURN.txt` flag file
7. `cb76ef4` fixed form-error flattening (`flatten_errors` in `forms.py`;
   `form.errors.flat()` doesn't exist on `ErrorDict`, and
   `FlatErrorMixin` was only flattening non-field errors), declared
   `PaymentForm.amount` explicitly (`min_value=1` — a
   `PositiveIntegerField`'s form field otherwise gets `min_value=0`),
   added `AddRecordTests` + `RecordsFilterTests` (27 tests, green), and
   this file
8. `3562470` `Decisions.md` + `README.md` rewrite
9. `7684ddd` refreshed this file after the doc commits
10. `f85d4c8` set the `pyproject.toml` description
11. `ae2927f` a note by the owner
12. `816825f` the features pass: GET filtering (records filter switched
    POST → GET, so filtered URLs are bookmarkable), pagination
    (`Paginator(qs, 25)`), CSV export (`RecordsCsvView`), borrowed-money
    direction toggle (`direction` ChoiceField), settle-up suggestions
    (`settle_up()`) and monthly stats (`monthly_stats()`) on the balances
    page
13. `0630429` IP-address logging (`ip_address` field + `client_ip()`
    helper, `0002` migration) and removed `AUTH_PASSWORD_VALIDATORS`.
    **This commit also introduced a group-buy split regression** — it
    switched the split from the non-payer `others` to `all_weights`, so
    the payer's weight consumed part of the total and the others
    received less than the purchase amount.
14. `4e824c9` fixed that group-buy split regression (the payer's weight
    is excluded again, so the others split the full amount), extracted
    the `apply_filters()` helper (shared by RecordsView and
    RecordsCsvView), dropped the unused `user` arg from `settle_up()`,
    added the group-purchase badge on records, the borrowed-money
    dynamic label, IP in the admin `list_display` + CSV export, a CSS
    `--hairline` fix, and 13 new tests (54 total, all green)

15. Deployment: `deploy/install.sh` (systemd + gunicorn + env file +
    nginx example), `deploy/update.sh` (pull, sync, migrate,
    collectstatic, restart via pidfile kill), `AdminUpdateView` in
    `views.py` (POST endpoint that spawns `update.sh` detached),
    admin dashboard "Update now" button (`templates/admin/index.html`
    override), `gunicorn~=23.0` added to `pyproject.toml`, settings
    env-var aware (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
    `DJANGO_ALLOWED_HOSTS`, `DJANGO_STATIC_ROOT`).

16. Multi-app restructure: `Dong/urls.py` with `app_name="dong"`,
    project `urls.py` reorganized (homepage at `/`, login/logout at
    project level, `include()` for each app), `templates/home.html`
    (app grid), `base.html` nav generalized with `{% block app_nav %}`,
    all Dong templates/views updated to `dong:` namespace,
    `LOGIN_REDIRECT_URL` → `'/'`.

17. Ejlas app: `Meeting` model (start/end datetime, place, attendees
    M2M), `WeekBoardView` (6-day Sat–Thu grid with week navigation),
    `AddMeetingView` (form + non-blocking conflict warnings),
    `services.py` (times_overlap, find_conflicts, find_week_conflicts),
    `MeetingForm`, `MeetingAdmin`, 2 templates, 9 tests, initial
    migration.

18. IP Calculator app: `ipcalc` (stateless, single page),
    `templates/ipcalc/calculator.html` with inline JS (ipToNum,
    numToIp, maskFromPrefix, compute, classify), CSS for the results
    grid.

### Not started
- Nothing blocking. All three apps are implemented; 63 tests pass.
  See §9 for remaining open questions.

## 8. The RETURN.txt protocol

`RETURN.txt` used to gate work while the owner was away. **The owner is
now back and has explicitly authorized committing changes** (they said
"commit your changes — you're allowed to"). So the old stop-and-ask
protocol no longer applies: commit in small logical steps as work is done
and keep this file updated. If the owner later says to hold off on
commits, respect that.

## 9. Open questions for the owner

Resolved since the last update:
- **Features pass** — done. Settle-up suggestions, monthly stats,
  pagination, CSV export, GET filtering and the borrowed-money toggle are
  all implemented and committed (see §7, items 12–14).
- **Records filter POST → GET** — done. `RecordsView` is now a
  `TemplateView` reading `request.GET`, so filtered URLs are bookmarkable.

Still open:
1. Review `Decisions.md` (updated) and the rewritten `README.md` —
   awaiting the owner's sign-off.
2. Django 6.0's `SECURE_CSP` exists but is off; `group_buy.html` has an
   inline `<script>` (the live split preview) that a strict CSP would
   block until it's moved to a static `.js` file.

## 10. Working conventions in this repo

- Small git commits per logical step; message style: imperative, no
  emoji, e.g. "Implement records, add-record and group-buy views".
- No code comments unless asked.
- Keep code simple/clean/elegant; prefer plain Django patterns over
  cleverness.
- Never read `sender` from client input in `add_record`.
- Keep frontend/backend rounding in lockstep.
