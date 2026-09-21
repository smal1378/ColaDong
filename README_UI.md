# Cola Dong — frontend handoff

Templates and one shared stylesheet. No build step, no JS framework. The
only JavaScript is ~50 lines on the split page for the live preview, and the
page still submits correctly with JS disabled. The IP Calculator page has
~80 lines of client-side subnet math.

```
templates/
  base.html          header + shared shell, every page extends this
  home.html          app picker (landing page)
  login.html
  balances.html      Dong: running balances + settle-up + monthly
  add_record.html    Dong: record a payment
  records.html       Dong: payment list with filters
  group_buy.html     Dong: split a group purchase
  ejlas/
    week.html        Ejlas: weekly meeting board
    add_meeting.html Ejlas: add meeting form
  ipcalc/
    calculator.html  IP Calculator: stateless subnet tool
static/css/
  coladong.css       shared across all apps
```

## Setup

1. Put `templates/` and `static/` where your settings already look for them.
2. Add `"django.contrib.humanize"` to `INSTALLED_APPS` — `balances.html` and
   `records.html` use `|intcomma` to group the thousands in 6-digit amounts.
3. `django.template.context_processors.request` must be on (it is by default).
   The header uses `request.resolver_match.url_name` to underline the current
   tab, which saves you passing an `active` variable to every view.
4. Name your URLs: `balances`, `records`, `add_record`, `group_buy`, `login`,
   `logout`. Rename them if you like, just update `{% url %}` in the templates.

Fonts load from Google Fonts. If you'd rather not hit the network, drop the two
`<link>` tags in `base.html` — the CSS falls back to system fonts cleanly.

## Conventions the UI assumes

- Amounts are **integers, whole dollars**. Inputs are `min=1 max=999999 step=1`.
- A balance is **signed, from the signed-in user's point of view**: positive
  means *they owe you*, negative means *you owe them*. Negative figures render
  red and in parentheses, the way a ledger does it.
- Any user object works — a plain `User`, a dict, a namedtuple. The templates
  read `.username` and optionally `.name`, and a missing `.name` falls back to
  the username on its own.

---

## 1. Header — `base.html`

Needs nothing but `user` (the auth context processor). Shows the username and a
"Sign out" button when authenticated, a "Sign in" button otherwise.

Sign-out is a **POST** form, because `LogoutView` has required POST since
Django 4.1.

Two extras it renders if you pass them:
- `error` — a string, shown as a red banner above the page content.
- `django.contrib.messages` — rendered as banners too, `error` tag turns red.

Set the page title from a child with `{% block title %}`.

## 2. `login.html`

| Context | Type | Notes |
|---|---|---|
| `error` | str | optional, your message on a failed login |
| `username` | str | optional, refills the field after a failure |
| `next` | str | optional, written to a hidden input |

POSTs `username`, `password` (and `next` if present). On success redirect to
`next` or `balances`; on failure re-render with `error`.

## 3. `balances.html`

| Context | Type | Notes |
|---|---|---|
| `balances` | list | one row per person |
| `net_balance` | int, signed | rendered on the double-ruled total line |

Each row in `balances`:

| Field | Type | Notes |
|---|---|---|
| `username` | str | |
| `name` | str | optional display name |
| `balance` | int, signed | **positive = they owe you**, negative = you owe them |

Rows with `balance == 0` render as "settled — ", so include them or don't, both
look right.

```python
def balances(request):
    rows = [...]  # [{"username": "sara", "balance": -12000}, ...]
    return render(request, "balances.html", {
        "balances": rows,
        "net_balance": sum(r["balance"] for r in rows),
    })
```

## 4. `add_record.html`

| Context | Type | Notes |
|---|---|---|
| `users` | iterable | the other users, for the "Paid to" dropdown |
| `today` | **str** | `date.today().isoformat()`, prefills the date field |
| `form` | dict | optional, refills after a failed submit |
| `error` | str | optional |

`form` keys: `receiver`, `amount`, `date`, `note` — pass `request.POST` straight
back in and it works.

POST fields: `receiver` (username), `amount` (int), `date` (`YYYY-MM-DD`),
`note` (may be empty). Redirect to `balances` on success.

> Note on `today`: pass it as a **string**, not a `date`. The `|date:` filter
> silently renders empty when it gets a string back from `request.POST`, so the
> template avoids it and just prints the value.

## 5. `records.html`

| Context | Type | Notes |
|---|---|---|
| `users` | iterable | fills both filter dropdowns |
| `records` | iterable | newest first |
| `filters` | dict | the filters currently applied, refills the form |
| `total_amount` | int | optional, sum of the filtered rows |

Each record: `.date` (a real `date`), `.sender`, `.receiver` (str or `User`),
`.amount` (int), `.note`.

`filters` keys: `sender`, `receiver`, `date_from`, `date_to` — empty string means
no constraint. Pass `{}` on first load.

The filter form POSTs back to the same URL with exactly those four field names.
"Clear all" is just a link back to the bare URL, so handle the unfiltered case
in your GET branch and you're done.

```python
def records(request):
    f = {k: request.POST.get(k, "") for k in ("sender", "receiver", "date_from", "date_to")}
    qs = Record.objects.select_related("sender", "receiver").order_by("-date", "-id")
    if f["sender"]:    qs = qs.filter(sender__username=f["sender"])
    if f["receiver"]:  qs = qs.filter(receiver__username=f["receiver"])
    if f["date_from"]: qs = qs.filter(date__gte=f["date_from"])
    if f["date_to"]:   qs = qs.filter(date__lte=f["date_to"])
    return render(request, "records.html", {
        "users": User.objects.order_by("username"),
        "records": qs,
        "filters": f,
        "total_amount": qs.aggregate(s=Sum("amount"))["s"] or 0,
    })
```

If you'd rather have shareable filter URLs, switch `method="post"` to `"get"`,
drop the `{% csrf_token %}`, and read `request.GET` instead. The field names
don't change.

## 6. `group_buy.html`

| Context | Type | Notes |
|---|---|---|
| `users` | iterable | **all** users, including the signed-in one |
| `today` | **str** | prefills the date |
| `form` | dict | optional: `payer`, `amount`, `date`, `note` |
| `error` | str | optional |

To refill the participant list after a failed submit, annotate each item in
`users` with `.selected` (bool) and `.weight`. Leave them off and everyone is
unchecked at `1×`, which is what you want on first load — so plain `User`
objects are fine here.

POST fields:

| Field | Notes |
|---|---|
| `payer` | one username, defaults to the signed-in user |
| `amount` | int, total paid |
| `date` | `YYYY-MM-DD` |
| `note` | optional |
| `participants` | repeated, one value per checked username |
| `weight_USERNAME` | one per checked username, e.g. `weight_sara = "2"` |

```python
names   = request.POST.getlist("participants")
weights = {n: Decimal(request.POST.get("weight_" + n) or "1") for n in names}
total_w = sum(weights.values())
# each participant owes the payer: amount * weights[n] / total_w
```

The page previews each person's share live using **largest-remainder rounding**,
so the parts always add back up to the total with no cents left over. Tell me
what rule you use server-side and I'll make the preview match it exactly.

The payer can be in the participant list or not — the UI doesn't care, and
either way the payer's own share nets out to zero against what they laid out.

---

## Things worth deciding before you wire it up

- **Duplicate prevention.** Nothing stops a double-submit on the two forms.
  Cheapest fix is a redirect after a successful POST, which the flow already
  assumes.
- **Self-payment.** `add_record.html` only lists other users, but nothing stops
  a crafted POST. Validate it server-side.
- **Editing and deleting records.** Not in the brief, so there's no UI for it.
  Say the word and I'll add a row action plus a confirm step.
- **Pagination on `records.html`.** The table takes any number of rows but gets
  unwieldy past a few hundred. Easy to add if you want it.