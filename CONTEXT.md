# Cola Dong — project context

This file exists so the repo is self-contained. `README.md` and
`BACKEND_GUIDE.md` cover *what to build and how*; this one covers
*why it's shaped this way* — the reasoning, conventions, and decisions
that came out of the planning conversation and aren't visible just from
reading the code. If you're a developer or an AI agent picking this repo
up cold, read this first.

---

## What this is

Cola Dong is a weekend project: a shared ledger for a friend group. Each
friend has a plain Django `User` account. The core mechanic, stated
exactly as the project's owner described it:

> if I pay you $100 today, it gets recorded, and then you owe me $100.
> If you then give someone else $100, they owe you $100 instead.

That's the whole domain. Everything else in the app is UI and
bookkeeping around that one mechanic, plus one extension of it: a group
purchase, where one person pays and several people owe them a share.

**The non-obvious part, worth stating plainly because it's easy to get
backwards:** recording a payment creates a debt in the *opposite*
direction from the money. If Alice pays Bob, Bob now owes Alice — Bob
received cash, Bob owes it back. This is a lending ledger, not a shared
expense-splitting ledger in the Splitwise sense, even though the group-buy
feature looks superficially like one. Get the sender/receiver direction
backwards anywhere in the code and every balance in the app flips sign.

## Division of labor and why

The project's owner is a backend developer with some Django experience,
currently an MSc student in AI and robotics, and deliberately chose to
write the Django backend themselves rather than have it generated —
the explicit goal was to use this project to get better at Django. The
frontend (six HTML templates plus one stylesheet) was written by Claude,
handed over with a documented context-variable contract so the two
halves could be built independently.

That division shapes both existing documents:

- **`README.md`** is the contract between them — exactly which context
  variables and POST fields each template expects, written from the
  frontend's point of view, so the backend has a fixed target to hit.
- **`BACKEND_GUIDE.md`** is a teaching document, not a solutions file —
  it explains the Django tools for each piece (constraints, `CreateView`,
  aggregation, `transaction.atomic()`) and shows small illustrative
  snippets, but deliberately stops short of the finished `models.py` and
  `views.py`, because writing those was the point of the exercise.

As of the last update to this file, the frontend (templates + CSS) is
complete. The backend is **not yet built** — the project had `startproject`
and `startapp` done, plus two GET-only class-based view stubs, when the
implementation guide was written. Check the actual repo state before
trusting that summary; this file won't update itself as the code changes.

## Design decisions and the reasoning behind them

### The UI's visual direction

The interface is built around a *greenbar accounting sheet* metaphor
deliberately, rather than a generic fintech-dashboard look — pale tinted
alternating rows, hairline rules, right-aligned monospaced figures, and a
double rule (`border: 3px double`) used specifically to mark anything
that totals up (page header, table footers, the split-page running total).
The double rule is meant to be the one recurring structural signature
across every page, and it should only ever appear where something is
actually finalized — don't reuse it as generic decoration.

Debts follow real accounting convention: money you owe renders in red and
in parentheses; money owed to you renders in plain ink. That convention
is implemented in `balances.html` and is worth preserving if you add
amounts anywhere else in the app — a debt that reads as a plain positive
number breaks the visual language the rest of the app relies on.

Palette and type are fixed choices, not arbitrary — see the `:root`
custom properties at the top of `static/css/coladong.css` for the exact
values (ledger paper, band, ink, hairline, red-ink) and the two font
families (Archivo for text, JetBrains Mono reserved for money and dates
only).

### Why one database table instead of two

`BACKEND_GUIDE.md` walks through this in detail, but the short version of
*why*: a direct payment and a group-purchase share are the same
underlying fact — "X now owes Y a specific amount, as of a specific
date, optionally because of some group purchase." Modeling them as one
`Payment` table with a nullable `group_purchase` foreign key means the
balances query, the records list, and the filters all work identically
regardless of which kind of event produced the row. The alternative
(two separate tables, unioned together for balances and the records
list) was considered and rejected for this project's scope — it would
mean writing and maintaining two query paths that need to agree with
each other, for no benefit this app currently needs.

### The balance sign convention

A balance is a single signed integer, from the viewpoint of whoever is
looking at it: **positive means they owe you, negative means you owe
them.** This was chosen over two separate unsigned "you owe" / "owed to
you" columns because it collapses cleanly to a real "net position" line
in the UI (the double-ruled total on `balances.html`), and because it
matches how a person actually thinks about a running tab with a friend —
one number, one direction.

### Amounts are whole-dollar integers, on purpose

The spec was explicit: 6-digit amounts, no floating point, $1 minimum.
This isn't a simplification to revisit later — it's a firm constraint
that should be enforced as an integer field with validators
(`PositiveIntegerField`, `MinValueValidator(1)`, `MaxValueValidator(999_999)`),
not a `DecimalField` rounded for display. Using an integer type makes
"no cents" true by construction instead of something every call site has
to remember to enforce.

### Rounding must match, frontend and backend

The group-buy split preview (client-side JS in `group_buy.html`) and the
backend's actual save both need to turn "a whole-dollar total split by
weighted shares" into whole-dollar parts that sum back to the total
exactly. Both sides use **largest-remainder rounding** — floor everyone's
exact share, then hand the leftover dollars one at a time to whoever's
fractional part was largest. `BACKEND_GUIDE.md` includes a direct Python
port of the same algorithm the JS preview uses
(`split_amount(total, weights)`). If you ever change the rounding rule on
one side, change it on both, or the number a user previews before
submitting will stop matching what actually gets saved.

### Trust boundaries, stated explicitly

Two deliberate, different decisions about whose word the backend takes:

- **`add_record` never accepts who the sender is from the client.** The
  form only asks for a receiver; the sender is always the logged-in user,
  set server-side (`form.instance.sender = self.request.user`), never
  read from POST data. Otherwise anyone could record a payment as having
  come from someone else.
- **`group_buy`'s payer field *is* selectable, and can be someone other
  than the logged-in user.** This is intentional, matching the original
  spec ("one user is selected as the sender") — the app is built for a
  small friend group on the honor system, and letting anyone log a
  purchase on a friend's behalf (e.g., recording that Bob paid for pizza
  even though Alice is the one filling in the form) was treated as a
  feature, not a gap. Worth reconsidering only if the trust model of the
  group ever changes.

### The `sender != receiver` rule lives in two places, deliberately

It's validated in the form layer and also enforced with a database
`CheckConstraint`. The constraint is the belt to the form's suspenders —
it protects the data against anything that writes to the table outside
the form path (a management command, a migration, a future API), not
just against a bad request.

## Environment specifics worth knowing up front

- Package management is **`uv`**, not plain `pip`/`venv`.
- Django version is **6.1.1**, released only recently — young enough that
  some tutorials and older Stack Overflow answers will show outdated
  APIs. One concrete trap already identified: `CheckConstraint`'s `check=`
  keyword was deprecated in Django 5.1 and **fully removed** in 6.0, so
  it must be written as `CheckConstraint(condition=...)` on this project
  or the app will fail to import, not just warn.
- Django 6.0 also shipped real Content-Security-Policy support
  (`SECURE_CSP` setting). It isn't enabled in this project, but if it
  ever is, note that `group_buy.html` has an inline `<script>` block for
  the live split-preview — a strict CSP would block it until that script
  is moved into its own static `.js` file.

## What's deliberately out of scope right now

These came up during planning and were explicitly deferred, not
forgotten:

- No editing or deleting of records — the original spec only asked for
  adding and viewing.
- No pagination on the records list.
- The records filter form POSTs rather than using GET, which means
  filtered views aren't bookmarkable or shareable by URL. Switching it
  to GET later is a small, contained change (drop the CSRF token, read
  `request.GET` instead of `request.POST`) — see `BACKEND_GUIDE.md` §7.
- No REST API — everything is server-rendered Django templates using
  context variables, by explicit preference, since it was judged easier
  to implement for this project's scope. An API can be layered in later
  for any specific page without changing the others.

## Where to look next

- **`README.md`** — the exact context variables and POST field names
  each template expects. Treat it as the source of truth for what the
  backend's views need to pass in and read out.
- **`BACKEND_GUIDE.md`** — a walkthrough of how to build the models,
  views, auth, balance queries, filtering, and the group-buy rounding
  and transaction logic, in the order it makes sense to build them.
- **`static/css/coladong.css`** — the `:root` block at the top is the
  full design-token list (colors, fonts) if the visual language needs to
  extend to a page that doesn't exist yet.
