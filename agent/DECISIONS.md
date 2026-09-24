# Decisions

## Data model

- One `Payment` table for both direct payments and group-buy shares, with a
  nullable `group_purchase` FK. Both are the same fact: “X owes Y an amount
  as of a date.”
- Balance is a single signed integer: positive = they owe you, negative =
  you owe them.
- Amounts are `PositiveIntegerField` (1–999999), not `DecimalField`, so
  “no cents” is true by construction.
- `sender != receiver` is enforced twice: in `PaymentForm.clean_receiver`
  and with a model `CheckConstraint`, so data written outside the form path
  is still protected.

## Trust and money direction

- `add_record` never reads sender from the client in the `paid` direction.
  Sender is always the logged-in user, set server-side.
- In the `borrowed` direction, the selected user is the sender: the user is
  recording that someone else paid them.
- The selected user in add-record is never the logged-in user; for `paid`
  they become receiver, and for `borrowed` they become sender.
- `group_buy` payer is selectable, including someone other than the
  logged-in user. This is intentional for a small honor-system friend group.

## Forms and views

- Templates receive a plain dict, not a form instance, via `refill_dict` in
  `forms.py`, so `form.receiver`-style template lookups keep working.
- Form errors are flattened into the single `error` string templates expect,
  via `flatten_errors` in `forms.py`, used by `FlatErrorMixin`,
  `RecordsView`, and `GroupBuyView`.
- `PaymentForm.amount` is declared explicitly with `min_value=1` and
  `max_value=999_999`; `PositiveIntegerField.form_field()` would otherwise
  yield `min_value=0` and drop the model's `MinValueValidator(1)`.
- The records filter is a GET `TemplateView`, so filtered views are
  bookmarkable and shareable. `query_string` carries active filter params
  into pagination links.
- Group-buy participants and weights are read from the request in the view,
  not as form fields, because weight inputs are named `weight_<username>`.
  The static top is a `GroupBuyForm`; the dynamic part is validated in
  `_save_split`.
- Group-buy save is wrapped in `transaction.atomic()`: the
  `GroupPurchase` row and all `Payment` shares commit or roll back together.
  The payer is excluded from the shares.

## Rounding

- Frontend split preview and backend `split_amount` both use
  largest-remainder rounding: floor every share, then distribute leftover
  whole dollars by largest fractional part.
- The two sides must stay in lockstep or previewed amounts stop matching
  saved amounts.

## Django traps

- `CheckConstraint` must use `condition=`; the old `check=` keyword was
  removed in Django 6.0 and fails import.
- `uv` manages the environment; run everything through `uv run …`.

## Testing

- Tests exercise the HTTP layer with `Client`, not just services, because
  error flattening and form bounds only show up through request/response.
- `split_amount` is property-tested over many (total, weights) pairs: parts
  are positive integers, sum exactly to the total, and differ by at most 1.

## Added features

- Records pagination, 25 per page, with filter params preserved via
  `query_string`.
- CSV export on the records page via `RecordsCsvView`; amounts are plain
  integers, no `$` prefix.
- Add-record direction toggle: `direction` ChoiceField (`paid` /
  `borrowed`) is form-only, not a model field. `form_valid` swaps sender and
  receiver for `borrowed`.
- Settle-up suggestions on the balances page via `settle_up()` in
  `services.py`: greedy matching of largest debtor with largest creditor.
  Sign convention is `sent - received`; positive = creditor, negative =
  debtor.
- Monthly stats on the balances page via `monthly_stats(user)` in
  `services.py`, grouping payments by month with `TruncMonth`.
- Group-purchase badge on the records page: `<span class="gp-badge">` when
  `r.group_purchase` is set.
- Client IP logging: each `Payment` row records the client IP at save time.
  `client_ip(request)` checks `X-Forwarded-For` first, then `REMOTE_ADDR`.
- Password validators disabled (`AUTH_PASSWORD_VALIDATORS = []`) because the
  friend group uses simple usernames and complexity rules added friction
  without security benefit at this scale.

## Multi-app restructure

- Namespaced URLs: each app's `urls.py` sets `app_name`; Dong URLs carry the
  `dong:` prefix. Project `urls.py` mounts apps under `/dong/`, `/ejlas/`,
  and `/ip/`.
- Homepage at `/` serves `home.html` with an app grid.
- `LOGIN_REDIRECT_URL` is `/`, so new users land on the app picker.
- Login/logout are project-level; all apps share one auth session.
- `base.html` uses `{% block app_nav %}` so each app can add sub-navigation.
- One shared CSS file, `ColaDong/Dong/static/css/coladong.css`, is used by
  all apps through staticfiles.
- Ejlas uses one `Meeting` model and no separate `Place` model; place is a
  `CharField`, and conflict detection compares case-insensitively.
- Ejlas conflict warnings are non-blocking; the meeting saves and conflicts
  are shown after save.
- Ejlas week starts Saturday (Iran calendar convention); Friday is the only
  weekend day. `week_start()` computes the Saturday on or before a date.
- Ejlas conflict detection: two meetings overlap if
  `a.start_time < b.end_time AND b.start_time < a.end_time`. Person conflict
  = shared attendee; place conflict = same non-empty `place`
  (case-insensitive). A meeting can have both types simultaneously.
  `find_conflicts(meeting, existing_meetings)` returns a list of conflict
  dicts.
- IP Calculator is entirely client-side: `TemplateView` serves the page,
  all subnet math runs in inline JS. It requires login like all other apps
  (site-wide auth).
- Ejlas week navigation uses prev/next arrows plus a "This week" link, not
  a date picker.

## Deployment

- No root or sudo at runtime. The systemd service runs as a dedicated
  non-root `RUN_USER`; `update.sh` runs as the same user.
- Service restart is root-free: `update.sh` signals the gunicorn master via
  its PID file (`SIGTERM`, 15 s wait, `SIGKILL` fallback); systemd uses
  `Restart=always`.
- Gunicorn uses `--pid ${LOG_DIR}/gunicorn.pid` so `update.sh` can find and
  signal the master process.
- `AdminUpdateView` spawns `deploy/update.sh` detached with
  `subprocess.Popen(..., start_new_session=True)` and returns 202 before
  gunicorn is killed. Logs go to `LOG_DIR` in production, with a dev
  fallback of `BASE_DIR/update.log`.
- Settings are env-var-driven: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
  `DJANGO_ALLOWED_HOSTS`, and `DJANGO_STATIC_ROOT` are read from the
  environment with dev-safe defaults; a production hardening block activates
  when `DEBUG=False`.

## Agent process

- The agent acts as the working decision-maker for implementation and doc
  choices, and logs important decisions here so the owner can review them
  later.
- When the user reports a context/loop risk, the loop-safe protocol is:
  persist known facts into `agent/`, then process source docs one file at a
  time, checking consistency before moving on.
- The old `RETURN.txt` stop-and-ask protocol is retired. Commits happen only
  when the owner explicitly asks for them in the current session.
- `apply_filters()` is the shared filter helper for `RecordsView` and
  `RecordsCsvView`, so CSV export and page filtering cannot drift apart.
- `settle_up()` takes no user argument; it computes global balances for all
  users and suggests group-wide settle-up transfers.
- The group-buy split regression from `0630429` was fixed in `4e824c9`:
  the payer's weight is excluded from the split, so the other participants
  split the full purchase amount.
- `AgentStartHere.md` claimed `TIME_ZONE = "Etc/UTC+3:30"`, but the current
  setting is `TIME_ZONE = 'UTC'`; agent notes record the current setting.

## Project shape

- Server-rendered Django templates, no REST API, by explicit preference.
- No record editing/deletion in Dong or Ejlas, by scope decision.
- Free-text place names in Ejlas; no `Place` model.
- `agent/` holds agent working memory; stable human docs stay at root.
- Docs use project-root-relative paths only, so the repo can move hosts.
- Root `CONTEXT.md` remains as the auto-load hook because the harness loads
  that file automatically.
