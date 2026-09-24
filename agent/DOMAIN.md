# Domain

## Project shape

ColaDong is a multi-app platform for a friend group, built as a weekend
project. Three apps share one Django project, one theme, and one auth
session:

- `Dong` — shared ledger; each friend has a plain Django `User` account.
- `Ejlas` — weekly meeting board, Saturday–Thursday, Iran calendar.
- `ipcalc` — stateless subnet calculator; all logic is client-side JS.

## Dong core mechanic

Dong is a lending ledger, not a Splitwise-style expense splitter.

- If Alice pays Bob $100, Bob now owes Alice $100.
- If Bob then gives someone else $100, that person now owes Bob $100.
- Recording a payment creates a debt in the opposite direction from the
  money.
- The group-buy feature looks like expense splitting, but it is still a
  lending fact: participants owe the payer their shares.

Getting sender/receiver direction backwards flips every balance in the app.

## Group purchases

A group purchase is one person paying for several people. Each participant
owes the payer a share. The share split uses largest-remainder rounding on
both frontend and backend.

## Balance sign convention

A balance is one signed integer from the viewpoint of the person looking at
it:

- Positive: they owe you.
- Negative: you owe them.

This was chosen over two unsigned columns because it collapses to a real
net-position line in the UI and matches how a person thinks about a running
tab with a friend.

`services.compute_balances(user)` returns one row per other user, ordered by
username and including zero-balance users. It computes outgoing and incoming
sums separately with `values().annotate(Sum("amount"))`, then merges them:
money sent to another user increases that user's balance, and money received
from another user decreases it. Each row is `{username, name, balance}`.

## Accounting visual language

The UI deliberately uses a greenbar accounting-sheet metaphor, not a generic
fintech-dashboard look.

- Pale tinted alternating rows.
- Hairline rules.
- Right-aligned monospaced figures.
- Double rule (`border: 3px double`) marks finalized totals only: page
  header, table footers, and the split-page running total.
- Do not reuse the double rule as generic decoration.
- Money you owe renders in red and in parentheses.
- Money owed to you renders in plain ink.
- This convention is implemented in `balances.html`; preserve it if amounts
  appear anywhere else.

Palette and fonts are fixed choices. The `:root` block at the top of
`ColaDong/Dong/static/css/coladong.css` is the design-token list: ledger
paper, band, ink, hairline, red ink, Archivo for text, and JetBrains Mono
for money and dates only. The stylesheet is shared by all three apps through
Django's staticfiles framework.

## Data model

A direct payment and a group-purchase share are the same underlying fact:
“X now owes Y a specific amount, as of a specific date, optionally because
of some group purchase.”

They are stored in one `Payment` table with a nullable `group_purchase`
foreign key. This keeps the balances query, records list, and filters
identical regardless of which kind of event produced the row. Two tables
would require two query paths that need to agree with each other, for no
benefit at this project's scope.

## Amounts

Amounts are whole-dollar integers, on purpose.

- 6-digit amounts.
- No floating point.
- $1 minimum.
- Enforced with `PositiveIntegerField`, `MinValueValidator(1)`, and
  `MaxValueValidator(999_999)`.
- Not a `DecimalField` rounded for display.

Using an integer type makes “no cents” true by construction.

## Rounding

The group-buy split preview (client-side JS in `group_buy.html`) and the
backend save must both turn a whole-dollar total split by weighted shares
into whole-dollar parts that sum back to the total exactly.

Both sides use largest-remainder rounding:

1. Floor everyone's exact share.
2. Distribute leftover dollars one at a time to the largest fractional
   parts.

`services.split_amount()` is the backend implementation. Frontend and
backend must always agree, or the preview no longer matches the saved
amount.

## Trust boundaries

Two deliberate, different decisions about whose word the backend takes:

- `add_record` never accepts sender from the client. The form posts the
  selected user as a username string (`to_field_name="username"`); in the
  `paid` direction that user becomes receiver and sender is always the
  logged-in user, set server-side as `form.instance.sender = request.user`,
  never read from POST data.
- The `direction` field (`paid` / `borrowed`) is form-only. For `borrowed`,
  `form_valid` swaps sender and receiver: the selected user becomes sender
  and the logged-in user becomes receiver.
- `group_buy` payer is selectable and can be someone other than the
  logged-in user. This is intentional, matching the original spec. The app
  is built for a small friend group on the honor system, so letting someone
  record a payment made by a friend is a feature, not a gap. Reconsider only
  if the trust model changes.

## `sender != receiver`

The rule is validated in the form layer and also enforced with a database
`CheckConstraint`. The constraint protects the data against anything that
writes to the table outside the form path: management commands, migrations,
or a future API.

## Deliberately out of scope

See `agent/BACKLOG.md` for the full list. Short version:

- No editing or deleting of records.
- No REST API.
- Ejlas has no meeting editing/deletion and no separate `Place` model.
