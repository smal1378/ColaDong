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
  - `uv run python manage.py test Dong`
  - `uv run python manage.py makemigrations` / `migrate`

### Django 6.x trap (already stepped on)
`CheckConstraint(check=...)` was removed in Django 6.0 — it must be
`CheckConstraint(condition=...)`. `models.py` uses `condition=`.

## 4. Repo layout

```
ColaDong/                     <- repo root (git lives here)
  ColaDong/                   <- Django project dir (manage.py is here)
    ColaDong/                 <- settings/urls
    Dong/                     <- the app
      models.py               Payment, GroupPurchase
      views.py                all views (CBV + plain View mix)
      forms.py                PaymentForm, RecordFilterForm, GroupBuyForm
      services.py             compute_balances(), split_amount()
      admin.py                both models registered
      tests.py                full test suite (~27 tests)
      migrations/0001_initial.py
    templates/                6 templates (base, login, balances, records,
                              add_record, group_buy) — the frontend contract
    static/css/coladong.css
  CONTEXT.md                  why things are shaped this way
  BACKEND_GUIDE.md            original build walkthrough
  README_UI.md                frontend handoff contract
  Decisions.md                implementation decision log
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
| `balances` | `balances` (list of dicts: username, name, balance), `net_balance` (int) |
| `records` | `users` (list of all User objects), `records` (list of Payment), `filters` (dict with sender/receiver/date_from/date_to), `total_amount` (int Sum of shown amounts) |
| `add_record` | `form` (refill dict), `error` (string, rendered by base.html) |
| `group_buy` | `users` (list of dicts: username, name, selected, weight), `form` (refill dict: payer/amount/date/note), `today` (YYYY-MM-DD string), `error` |
| `login` | standard auth context + flat `error` string |

POST field names:
- `add_record`: `receiver` (username string), `amount`, `date`, `note`
- `records` filter (POST form): `sender`, `receiver`, `date_from`, `date_to`
- `group_buy`: `payer` (username), `amount`, `date`, `note`,
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

### Not started
- A "features pass" the owner asked for once the core is stable
  (ideas floated: settle-up suggestions on balances, monthly stats).
  Owner is out of town; see §8 before starting new features.

## 8. The RETURN.txt protocol (IMPORTANT)

The owner is away and may come back at any time. `RETURN.txt` contains
`False` while they're out. **Check it frequently** (e.g. before each
commit). If its content changes to `True` or any "I'm back" text:
1. Stop starting new work.
2. Give a clear status update of everything done.
3. Ask the owner questions about open decisions (see §9).

## 9. Open questions for the owner

1. Features pass: which ideas (settle-up suggestions? stats? pagination?)
2. Review `Decisions.md` and the rewritten `README.md` — written, awaiting
   the owner's sign-off.
3. The records filter form POSTs (not GET) so filtered URLs aren't
   bookmarkable — switch to GET? (small contained change)
4. Django 6.0's `SECURE_CSP` exists but is off; `group_buy.html` has an
   inline `<script>` that a strict CSP would block.

## 10. Working conventions in this repo

- Small git commits per logical step; message style: imperative, no
  emoji, e.g. "Implement records, add-record and group-buy views".
- No code comments unless asked.
- Keep code simple/clean/elegant; prefer plain Django patterns over
  cleverness.
- Never read `sender` from client input in `add_record`.
- Keep frontend/backend rounding in lockstep.
