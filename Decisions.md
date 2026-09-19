# Decisions

A log of the implementation decisions made while building the backend, and
why. Domain-level rationale (the lending-ledger direction, the greenbar
visual language, the trust model) lives in `CONTEXT.md`; this file covers
choices about *how the code is shaped*.

## Data model

- **One `Payment` table for both direct payments and group-buy shares**,
  with a nullable `group_purchase` FK. A share is the same underlying fact
  as a direct payment — "X owes Y an amount as of a date" — so balances,
  the records list, and the filters all work identically regardless of
  which kind of event produced the row. Two tables would mean two query
  paths that have to agree with each other, for no benefit at this scope.
- **Balance is a single signed integer**, positive = they owe you,
  negative = you owe them. Collapses cleanly to the net-position line on
  the balances page and matches how a person thinks about a running tab.
  Two unsigned columns would have been redundant.
- **Amounts are `PositiveIntegerField` (1–999999), not `DecimalField`.**
  "No cents" is then true by construction instead of something every call
  site must remember to enforce.
- **`sender != receiver` is enforced twice**: in `PaymentForm.clean_receiver`
  and with a `CheckConstraint` on the model. The form catches it for users;
  the constraint protects the table against anything writing outside the
  form path (management commands, migrations, a future API).

## Trust boundaries

- **`add_record` never reads the sender from the request** in the `paid`
  direction. The form only asks for a receiver; the sender is always the
  logged-in user, set server-side. In the `borrowed` direction the
  selected user *is* the sender (they paid the logged-in user), which is
  the intended behavior — the user is recording that someone else paid them.
  The receiver dropdown excludes the signed-in user for `paid`; for
  `borrowed` it includes them (the sender dropdown includes everyone except
  the logged-in user in that direction).
- **`group_buy`'s payer *is* selectable**, including someone other than the
  logged-in user. Deliberate: the app is for a small friend group on the
  honor system, and logging a purchase on a friend's behalf is a feature
  (see `CONTEXT.md`).

## Forms and views

- **The templates receive a plain dict, not a form instance**, for
  refilling inputs after an error (`refill_dict` in `forms.py`). The
  frontend was written first against that contract; passing a Django form
  object would break `form.receiver`-style template lookups.
- **Form errors are flattened into the single `error` string the templates
  expect** (`flatten_errors` in `forms.py`, used by `FlatErrorMixin`,
  `RecordsView`, and `GroupBuyView`). Templates have no Django-form error
  markup — the whole contract is one `error` variable.
- **`PaymentForm.amount` is declared explicitly** with `min_value=1,
  max_value=999_999`. A `PositiveIntegerField`'s `form_field()` yields
  `min_value=0` and drops the model's `MinValueValidator(1)`, so without
  the explicit declaration the form would accept 0 and its error message
  would say "0" instead of "1".
- **The records filter is a `TemplateView` with GET**, not a POST form.
  Filtered views are bookmarkable and shareable by URL. The `query_string`
  context var carries the current filter params (minus `page`) into the
  pagination links so filtering survives page changes.
- **Group-buy participants and weights are read from the request in the
  view**, not as form fields: the weight inputs are named `weight_<username>`,
  so their field names are dynamic. The static top of the form (payer,
  amount, date, note) *is* a `GroupBuyForm`; the dynamic part is validated
  by hand in `_save_split`.
- **The group-buy save is wrapped in `transaction.atomic()`**: the
  `GroupPurchase` row and all its `Payment` shares commit or roll back
  together. The payer is excluded from the shares — they paid, they owe
  nobody from this purchase.
- **The records filter is a `TemplateView` with GET**, not a POST form.
  Filtered views are bookmarkable and shareable by URL. The `query_string`
  context var carries the current filter params (minus `page`) into the
  pagination links so filtering survives page changes.

## Django version traps

- **Django 6.0 removed the `CheckConstraint(check=...)` keyword**
  (deprecated in 5.1). Must be `CheckConstraint(condition=...)` — with the
  old keyword the app fails at import, it doesn't just warn.
- **`uv` manages the environment**, not `pip`/`venv`. Run everything
  through `uv run …`.

## Rounding

- **Largest-remainder rounding, identical on both sides.** The JS preview
  in `group_buy.html` and `split_amount` in `services.py` implement the same
  algorithm: floor every share, then hand out the leftover whole dollars to
  the largest fractional parts. If one side's rule changes, the other must
  change too, or the previewed amounts stop matching the saved ones.

## Testing

- **Tests exercise the HTTP layer** (`Client`), not just the services —
  the failure modes that actually bit us (error flattening, form field
  bounds) only show up through a request/response round trip.
- **`split_amount` is property-tested** over many (total, weights) pairs:
  parts are positive integers, sum exactly to the total, and the difference
  between any two parts is at most 1.
- Run with `uv run python manage.py test Dong` from the `ColaDong/`
  directory.

## Added features (Sep 2026)

- **Pagination** (25 per page) on the records list. The filter params are
  carried through via a `query_string` context var so pagination links
  preserve the active filters.
- **CSV export** on the records page. `RecordsCsvView` is a plain
  `View(LoginRequiredMixin, View)` that applies the same filter logic as
  `RecordsView` and streams a `text/csv; charset=utf-8` response. Amounts
  are plain integers (no `$` prefix). The export link appears in the
  pagehead alongside the filter form.
- **Borrowed money (direction toggle)** on the add-record form. A
  `direction` ChoiceField (`paid` / `borrowed`) is form-only, not a model
  field. When `borrowed` is selected, `form_valid` swaps sender and
  receiver: the logged-in user becomes the receiver and the selected user
  becomes the sender. The sender dropdown is still excluded for `paid`
  but included for `borrowed` (you can record that someone else paid you).
- **Settle-up suggestions** on the balances page. `settle_up(user)` in
  `services.py` uses a greedy algorithm: sort creditors descending, sort
  debtors ascending, match the largest pair, repeat. The sign convention
  is `sent - received` (positive = creditor, negative = debtor).
- **Monthly stats** on the balances page. `monthly_stats(user)` in
  `services.py` uses `TruncMonth` to group payments by month, showing
  total sent and received with counts, most recent first.
