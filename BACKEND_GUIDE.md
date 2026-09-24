# Cola Dong — backend guide

> **Status:** this guide was written *before* the backend was implemented,
> as a teaching walkthrough for the owner to build against. The backend is
> now built and tested (63 tests, all three apps). Keep it as a reference
> for *how* the pieces work — but treat the code, `README_UI.md`, and
> `agent/DECISIONS.md` as the source of truth, not the snippets here (a few
> have drifted, e.g. the records filter is now GET and URL names carry the
> `dong:` namespace).

This is a map, not the code. Everywhere it matters I'll tell you the Django
tool for the job and show a *small* illustrative snippet — not the finished
view or model — so you're the one writing `models.py` and `views.py`. Where
I do give runnable code (the rounding function, a couple of test cases)
it's because that code is a self-contained utility, not "the app."

Read it top to bottom once, then use it as a reference while you build.
I've ordered it in the sequence I'd actually build this in.

A note on the version: you're on **Django 6.1.1**, released this August —
after my own training data ends, so I looked up what's actually new before
writing this rather than guessing. Two things from that research matter
directly for you and are called out inline: the syntax for model constraints
changed two releases ago (`condition=`, not `check=` — using the old kwarg
will crash on import, not just warn), and Django 6.0 shipped a real
Content-Security-Policy feature that's relevant because `group_buy.html`
has an inline `<script>` block.

---

## 0. The shape of the thing

Six pages, six things the server needs to do:

| Page | URL name | What it needs |
|---|---|---|
| Sign in | `login` | Django's built-in auth view, lightly wrapped |
| Balances | `balances` | a read-only aggregation query |
| Payments list | `records` | a filtered, paginated list, filters via GET |
| Add a payment | `add_record` | a `ModelForm`, one row created |
| Split a purchase | `group_buy` | custom POST parsing, several rows created atomically |
| Sign out | `logout` | Django's built-in view, POST-only |

Everything hangs off **one idea**: a payment record is a direction. When you
record "I paid Sara $100," what actually happened financially is *Sara now
owes you $100*. Your spec says this explicitly — paying someone creates a
debt in the other direction. A group split is the same primitive repeated:
the payer paid, so every participant now owes the payer their share.

That means you don't need two different tables for "payments" and "group
splits." A group split is just several payment rows created in one
transaction, tagged with which purchase they came from. One table, one
balance calculation, reused everywhere. I'll build the guide around that
design — it's not the only valid one, but it's the one that keeps your
`records` page and your balance math from needing two code paths.

---

## 1. Settings, before you write a line of view code

Go through this checklist now. Half of the confusing bugs in a first Django
project are a missing setting, not a logic error.

**`AUTH_USER_MODEL`.** You're using the plain `django.contrib.auth.User`,
which matches your spec exactly ("simple Django User account") — fine,
don't overthink it. The one thing worth knowing: Django's own docs are
insistent that if you *ever* think you might want a custom user model,
set it up before your first `migrate`, because swapping it out later means
rewriting every migration that touches `User`. For a weekend project with
no custom fields planned, sticking with the default is the right call —
just make it a deliberate choice, not a default you fell into.

**Templates.** I delivered a flat `templates/` folder (`base.html`,
`login.html`, etc., no subfolder). Point Django at it explicitly:

```python
TEMPLATES = [{
    ...
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    ...
}]
```

If you'd rather follow Django's own convention (each app owns
`app_name/templates/app_name/...`, which avoids two apps shadowing each
other's `base.html`), move the files into that layout instead and skip
`DIRS`. Either is fine at your scale — just pick one on purpose.

**Static files.** `django.contrib.staticfiles` needs to be in
`INSTALLED_APPS` (it is, by default) and needs to know where your CSS
lives:

```python
STATICFILES_DIRS = [BASE_DIR / "static"]
```

That's the folder containing `css/coladong.css`. In dev, `runserver` serves
it automatically through `staticfiles`; you don't need `collectstatic`
until you deploy somewhere.

**`django.contrib.humanize`.** Add it to `INSTALLED_APPS` — both
`balances.html` and `records.html` use the `|intcomma` filter to group
thousands in a 6-digit amount, and that filter lives in `humanize`.

**Auth redirects.**

```python
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"   # the project now lands you on the app picker at /
LOGOUT_REDIRECT_URL = "login"
```

`LOGIN_URL` is what `LoginRequiredMixin` sends anonymous users to.
`LOGIN_REDIRECT_URL` is where a successful login goes *if* there was no
`?next=` param. `LOGOUT_REDIRECT_URL` is where `LogoutView` sends people
once signed out. (In the shipped code the URLs are namespaced — Dong's
patterns live under `dong:`, so balances is `reverse_lazy("dong:balances")`
— but the setting names work the same.)

**Messages.** `django.contrib.messages` needs its app, its middleware, and
its context processor — all three are in Django's default `startproject`
output, so you likely already have them. Confirm rather than assume:

```python
INSTALLED_APPS = [..., "django.contrib.messages", ...]
MIDDLEWARE = [..., "django.contrib.messages.middleware.MessageMiddleware", ...]
TEMPLATES = [{
    "OPTIONS": {
        "context_processors": [
            ...,
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]
```

`base.html` already loops over `{% for message in messages %}`, so once
this is wired up, `messages.success(request, "Payment saved.")` in a view
just works — no template changes needed.

**Secrets.** `startproject` puts a real `SECRET_KEY` straight into
`settings.py` in plaintext, which is fine for a weekend project you're not
pushing to a public repo, but it's worth building the habit now since it
costs nothing:

```
uv add python-decouple
```

```python
from decouple import config
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
```

Then a `.env` file (gitignored) holding `SECRET_KEY=...` and `DEBUG=True`
locally. `django-environ` is the other popular choice here if you want
typed `DATABASE_URL`-style config later — either is a reasonable pick.

**One thing to flag now, fix later: Content-Security-Policy.** Django 6.0
added first-class CSP support (`SECURE_CSP` setting,
`ContentSecurityPolicyMiddleware`). It's opt-in — nothing breaks if you
never touch it — but if you ever *do* turn it on for this project, a
strict `default-src 'self'` policy will silently block the inline
`<script>` block at the bottom of `group_buy.html`, because inline scripts
are exactly what CSP exists to stop. Not something to fix today; just
know where to look if the split-preview JS mysteriously stops running
after you harden the settings later. The fix when you get there is moving
that script into its own `static/js/group_buy.js` file.

---

## 2. Modeling — `models.py`

One app-level decision first: **`Payment` is the only table you need.**

```python
class Payment(models.Model):
    sender = models.ForeignKey(User, on_delete=models.PROTECT, related_name="payments_sent")
    receiver = models.ForeignKey(User, on_delete=models.PROTECT, related_name="payments_received")
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999_999)])
    date = models.DateField()
    note = models.CharField(max_length=200, blank=True)
    group_purchase = models.ForeignKey(
        "GroupPurchase", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="shares",
    )
```

Walking through the choices:

- **`PositiveIntegerField`, not `DecimalField`.** Your spec is explicit:
  whole dollars, no floating point. An integer field makes "no cents"
  true by construction instead of something you have to keep checking for.
  `MinValueValidator(1)` and `MaxValueValidator(999_999)` enforce the
  "$1 to 6 digits" rule — but note validators only run through `full_clean()`
  (which `ModelForm.is_valid()` calls for you); they do **not** run on a
  bare `.save()`. More on that below.

- **`on_delete=models.PROTECT`, not `CASCADE`.** If someone's `User` account
  is ever deleted, do you want their entire payment history vanishing with
  them? `PROTECT` refuses the delete instead, which is almost always what
  you want for a financial ledger — you'd rather get an error and think
  about it than silently lose records. Django 6.1 also added **database-level**
  delete options (`DB_CASCADE`, `DB_PROTECT`, etc.) that push the same logic
  into the SQL `ON DELETE` clause instead of Python — worth knowing exists,
  not something you need for a project this size.

- **`group_purchase` is nullable.** A plain "I paid you" record has no
  purchase behind it; a group-split row does. This one field is what lets
  `records.html` show both kinds without any special-casing — they're the
  same row shape either way.

- **A sender cannot be their own receiver.** Django won't catch this for
  you automatically; enforce it at the database level with a constraint:

  ```python
  class Meta:
      ordering = ["-date", "-id"]
      constraints = [
          models.CheckConstraint(
              condition=~models.Q(sender=models.F("receiver")),
              name="payment_sender_is_not_receiver",
          ),
      ]
  ```

  **This is the one place your Django version matters directly.** The
  keyword used to be `check=`; it was deprecated in 5.1 and **fully removed**
  in 6.0. On 6.1.1, `CheckConstraint(check=...)` isn't a warning, it's a
  `TypeError`. Use `condition=`.

  Why bother with a DB constraint when you're also going to validate this
  in a form? Because the form only protects requests that go through the
  form. A constraint protects the data no matter what writes it — a bad
  migration, a management command you write in six months, a bug in a view
  you haven't written yet. Defense in depth, cheap to add, easy to forget.

`GroupPurchase` is thinner — mostly a label the individual `Payment` rows
point back to:

```python
class GroupPurchase(models.Model):
    payer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="purchases_paid")
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999_999)])
    date = models.DateField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Your turn:** write these two classes yourself (typing them out is where
the learning happens), then:

```
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Open the generated migration file in `migrations/0001_initial.py` before
running it. Reading a migration you didn't write by hand is a good habit —
you'll start to recognize what each field and `Meta` option turns into, and
you'll catch a typo before it's in your database instead of after.

> **Checkpoint.** Run `uv run python manage.py migrate` twice in a row.
> The second run should say "No migrations to apply" — migrations are
> supposed to be idempotent. If it tries to do something the second time,
> something's off.

---

## 3. Django admin — five minutes, huge payoff

Before writing a single view, register your models so you can see and
create data through a UI Django gives you for free:

```python
# admin.py
from django.contrib import admin
from .models import Payment, GroupPurchase

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "sender", "receiver", "amount", "group_purchase")
    list_filter = ("date",)
    autocomplete_fields = ("sender", "receiver")

admin.site.register(GroupPurchase)
```

`autocomplete_fields` matters once you have more than a handful of users —
it swaps the default `<select>` (which renders every user, always) for a
searchable widget. It needs `search_fields` defined on `UserAdmin`, which
Django's built-in one already has, so it works out of the box.

```
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Visit `/admin/`, create three or four test users and a handful of payments
between them by hand. You'll build and test your balances query against
real rows instead of guessing.

---

## 4. Authentication

Don't write a login view from scratch — subclass Django's:

```python
from django.contrib.auth.views import LoginView

class ColaLoginView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True
```

That's close to everything. `LoginView` is itself a `FormView` wrapping
`AuthenticationForm`; it already handles checking the password, calling
`django.contrib.auth.login()`, respecting `?next=`, and redirecting to
`LOGIN_REDIRECT_URL` on success.

The one gap: `login.html` renders a single `error` string, not Django's
usual `{{ form.errors }}`. You have two honest options, and either is a
legitimate choice — pick the one that fits how you want to grow this app:

**Option A — adapt the template to Django's own error surface.** Add
`{{ form.non_field_errors }}` to `login.html` where `error` currently
renders. This is the more idiomatic Django path and it scales — if you
ever add per-field errors, they're already there.

**Option B — keep the template's contract, translate in the view.**
Override `form_invalid` to flatten Django's error structure into the
plain string the template already expects:

```python
def form_invalid(self, form):
    context = self.get_context_data(form=form)
    context["error"] = " ".join(form.non_field_errors())
    return self.render_to_response(context)
```

Worth noticing: **you'll want this exact pattern again** for
`add_record`'s `ModelForm`, since that template also expects a plain
`error` string. If you go with Option B, you'll write the same four lines
twice — a sign you could lift it into a small mixin:

```python
class FlatErrorMixin:
    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["error"] = " ".join(form.non_field_errors())
        return self.render_to_response(context)
```

...then `class ColaLoginView(FlatErrorMixin, LoginView)` and
`class AddRecordView(FlatErrorMixin, LoginRequiredMixin, CreateView)`
both get it for free. You don't have to do this on the first pass — but
once you've written the same four lines twice, that's the signal to
extract it, and it's worth feeling that signal rather than being told
about it in advance.

Logout needs no view at all — `django.contrib.auth.views.LogoutView` is
POST-only since Django 4.1, which is exactly what `base.html`'s sign-out
form already sends:

```python
# urls.py
from django.contrib.auth.views import LogoutView
path("logout/", LogoutView.as_view(), name="logout"),
```

Finally: every other view needs `LoginRequiredMixin` (or the
`@login_required` decorator on a function view). Put it **first** in the
base-class list — mixin ordering matters in Python's MRO, and
`LoginRequiredMixin` needs to intercept `dispatch()` before your view logic
runs:

```python
class BalancesView(LoginRequiredMixin, TemplateView):
    ...
```

---

## 5. The two views you already have

You said you've got two class-based views with a bare `get()` returning
`render()`. That's the right starting shape for `TemplateView` — you're
one step away from a working `BalancesView` and probably `RecordsView` or
`AddRecordView`. The pattern for all of these is: override
`get_context_data()` to build the context dict, and let `TemplateView`
handle the rendering. You almost never need to write `render()` by hand
once you're in a `TemplateView`.

```python
class BalancesView(LoginRequiredMixin, TemplateView):
    template_name = "balances.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["balances"] = self._compute_balances(self.request.user)
        context["net_balance"] = sum(row["balance"] for row in context["balances"])
        return context
```

(`self._compute_balances` — you'll write this in the next section.)

For pages that need to handle a POST too (`records`, `add_record`,
`group_buy`), you have a choice of two shapes:

**Plain `View` with explicit `get()`/`post()`.** You write both methods
yourself, sharing a private helper for the context-building so you're not
duplicating it. This is the most transparent option — you can see exactly
what happens on each verb — and it's what I'd reach for on the `records`
filter page and the `group_buy` page, since both of those do custom
parsing that doesn't map cleanly onto a generic view.

```python
class RecordsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "records.html", self._context(request, filters={}))

    def post(self, request):
        filters = self._read_filters(request.POST)
        return render(request, "records.html", self._context(request, filters))

    def _context(self, request, filters):
        ...  # build users/records/filters/total_amount here, shared by both

    def _read_filters(self, data):
        ...  # pull sender/receiver/date_from/date_to out of a Form, see §7
```

**Generic `CreateView`.** For `add_record` specifically, this one's worth
using — it's a single `ModelForm` with no custom parsing, which is exactly
what `CreateView` exists for:

```python
class AddRecordView(FlatErrorMixin, LoginRequiredMixin, CreateView):
    model = Payment
    fields = ["receiver", "amount", "date", "note"]
    template_name = "add_record.html"
    success_url = reverse_lazy("dong:balances")

    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)
```

That `form_valid` override is the important line, and it's a small
security point, not just plumbing: **the template never asks the user who
the sender is** — there's no `sender` field on the form at all, on purpose.
If you instead trusted a posted `sender` value, anyone could submit a
payment recorded as coming from someone else. Setting
`form.instance.sender = self.request.user` before saving is what makes
"you can only ever record what *you* paid" true, rather than something you
hope the frontend enforces.

Also add `users` and `today` to the context for the template's dropdown
and date default — override `get_context_data` same as above.
Remember: `today` needs to be a **string** (`date.today().isoformat()`),
not a `date` object — I noted why in the template comments, but the short
version is Django's `|date:` filter silently blanks out when it receives
a plain string back from a refilled form, so the template just prints the
value as-is and expects you to hand it one already formatted.

---

## 6. Computing balances

This is the part worth spending real time on, because there are two ways
to write it and the difference teaches something.

**Version one — obvious, and fine to start with.** For each other user,
run two aggregate queries and subtract:

```python
from django.db.models import Sum

def compute_balances(user):
    others = User.objects.exclude(pk=user.pk)
    rows = []
    for other in others:
        they_owe_me = Payment.objects.filter(
            sender=user, receiver=other
        ).aggregate(total=Sum("amount"))["total"] or 0

        i_owe_them = Payment.objects.filter(
            sender=other, receiver=user
        ).aggregate(total=Sum("amount"))["total"] or 0

        rows.append({
            "username": other.username,
            "balance": they_owe_me - i_owe_them,
        })
    return rows
```

This is correct and completely readable. Its cost: **2N+1 queries** for N
other users — one to list the users, then two more per user. Fine for
five friends. Worth noticing as a pattern before it's fine for five
hundred.

**Version two — two queries total, independent of N.** Instead of asking
"for this one user, how much," ask the database once for *all* outgoing
totals grouped by receiver, and once for all incoming totals grouped by
sender, then merge the two small result sets in Python:

```python
def compute_balances(user):
    outgoing = (
        Payment.objects.filter(sender=user)
        .values("receiver__username")
        .annotate(total=Sum("amount"))
    )
    incoming = (
        Payment.objects.filter(receiver=user)
        .values("sender__username")
        .annotate(total=Sum("amount"))
    )

    net = {}
    for row in outgoing:
        net[row["receiver__username"]] = net.get(row["receiver__username"], 0) + row["total"]
    for row in incoming:
        net[row["sender__username"]] = net.get(row["sender__username"], 0) - row["total"]

    return [{"username": name, "balance": bal} for name, bal in net.items()]
```

`values(...).annotate(...)` is the ORM's `GROUP BY` — it's worth sitting
with `outgoing.query` in the shell (`print(outgoing.query)`) to see the
actual SQL it generates. That habit — checking what a queryset *actually*
runs — will save you more debugging time than almost anything else in
Django, because the ORM's laziness means a typo in a filter often fails
silently rather than loudly.

If you want a users list that includes people with a **zero** balance
(someone you've never transacted with, or someone you're now settled up
with), you'll need to start from `User.objects.exclude(pk=user.pk)` and
left-join in the net dict, defaulting missing entries to `0` — a small
but real difference from only showing users who appear in the two
querysets above.

A genuine stretch goal, not required: this can be done as a **single**
query using conditional aggregation (`Sum(Case(When(...)))`) or a
`.union()` of two annotated querysets. It's a nice exercise once the
two-query version works and you want to see how far the ORM can go before
you'd reach for raw SQL — but don't let it block you from moving on.

> **Checkpoint.** In the shell (`uv run python manage.py shell`), create
> two users and one `Payment` between them, then call `compute_balances()`
> for each and confirm the numbers are exact opposites of each other. If
> they're not, you've got a sign flipped somewhere — better to catch that
> now than after `group_buy` is generating rows too.

---

## 7. The filter form on `records.html`

Use a plain `forms.Form` (not a `ModelForm` — you're not creating a
`Payment`, you're validating four optional query parameters):

```python
class RecordFilterForm(forms.Form):
    sender = forms.ModelChoiceField(queryset=User.objects.all(), required=False, to_field_name="username")
    receiver = forms.ModelChoiceField(queryset=User.objects.all(), required=False, to_field_name="username")
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)
```

`to_field_name="username"` matters here: your `<select>` options post the
*username* as the value (look at `records.html` — `value="{{ u.username }}"`),
not the numeric primary key that `ModelChoiceField` expects by default.
Without this, a valid selection will fail validation for a confusing
reason.

Build the queryset from whatever cleaned data is present — don't filter on
a field that wasn't submitted:

```python
def filtered_records(form):
    qs = Payment.objects.select_related("sender", "receiver")
    data = form.cleaned_data if form.is_valid() else {}

    if data.get("sender"):
        qs = qs.filter(sender=data["sender"])
    if data.get("receiver"):
        qs = qs.filter(receiver=data["receiver"])
    if data.get("date_from"):
        qs = qs.filter(date__gte=data["date_from"])
    if data.get("date_to"):
        qs = qs.filter(date__lte=data["date_to"])
    return qs
```

`select_related("sender", "receiver")` is worth understanding, not just
copying: without it, rendering `{{ r.sender }}` for 50 rows in the
template triggers 50 *extra* queries — one per row, fetching the related
`User` lazily, the moment the template touches `.sender`. `select_related`
does a SQL `JOIN` up front instead, so the whole page is 1 query instead
of 51. This exact pattern — N+1 queries appearing only when you render the
template, not when you build the queryset — is probably the single most
common Django performance bug, and it's invisible until you look at the
query log or the debug toolbar.

`records.html`'s filter form now uses **GET**, not POST — the shipped
`RecordsView` reads `request.GET` and paginates 25 rows per page, so
filtered views are bookmarkable and shareable by URL. That's the state the
guide originally suggested as a future option; it's what's deployed now.
(And if that ever bothers you in reverse, the change is small: switch the
form's `method` back to `"post"`, re-add the `{% csrf_token %}`, and read
`request.POST` instead of `request.GET`. The field names don't change
either way.)

---

## 8. Splitting a purchase

Two real problems here, and they're worth treating as separate steps:
turning form data into whole-dollar shares that add up exactly, and then
saving several rows as one atomic unit.

**The rounding.** `$100 / 3` doesn't divide evenly, and you can't have a
$33.33 row in an integer column. The frontend's live preview already
solves this with *largest-remainder rounding* — give everyone their
rounded-down share, then hand the leftover dollars one at a time to
whoever's fractional part was closest to rounding up. Your backend needs
the exact same rule, or the number the user previewed won't match what
gets saved. Here's a direct Python port of the same algorithm:

```python
from decimal import Decimal

def split_amount(total: int, weights: dict[str, Decimal]) -> dict[str, int]:
    """Split `total` whole dollars across `weights`, proportionally,
    landing on whole dollars that always sum back to `total` exactly."""
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("weights must sum to a positive number")

    exact = {name: total * w / total_weight for name, w in weights.items()}
    floor = {name: int(v) for name, v in exact.items()}
    remainder = total - sum(floor.values())

    # give the leftover dollars to whoever's fractional part was largest
    order = sorted(exact, key=lambda name: exact[name] - floor[name], reverse=True)
    for name in order[:remainder]:
        floor[name] += 1

    return floor
```

This is small and self-contained enough to unit-test directly — do that
(see §9) before wiring it into a view. It's exactly the kind of function
that's miserable to debug through the browser and trivial to debug in
isolation.

**The save.** A group split touches two tables — one `GroupPurchase` row
and several `Payment` rows — and you don't want half of that written if
something fails partway through (a bad weight, a duplicate participant,
whatever). That's what `transaction.atomic()` is for:

```python
from django.db import transaction

with transaction.atomic():
    purchase = GroupPurchase.objects.create(
        payer=payer, amount=amount, date=date, note=note,
    )
    Payment.objects.bulk_create([
        Payment(sender=payer, receiver=user, amount=share,
                date=date, note=note, group_purchase=purchase)
        for user, share in shares.items()
        if user != payer  # the payer never owes themself
    ])
```

Everything inside the `with` block either all commits or all rolls back —
if `bulk_create` raises partway through, you won't end up with an orphan
`GroupPurchase` and no `Payment` rows pointing at it.

Two things worth deciding deliberately rather than by accident:

- **The payer can appear in the participant list** (the template lets you
  check the payer's own box) — that's fine conceptually, it just means
  "the payer's own share of the purchase," and the `if user != payer` guard
  above is what stops that from generating a nonsensical self-payment.
- **Parsing the dynamic `weight_<username>` fields.** These aren't a
  standard Django form field — they're built by the frontend per-checkbox.
  Read them straight off `request.POST`:

  ```python
  names = request.POST.getlist("participants")
  weights = {
      name: Decimal(request.POST.get(f"weight_{name}") or "1")
      for name in names
  }
  ```

  Wrap the `Decimal(...)` call in a `try/except (InvalidOperation, ...)`
  — this is user input, and `Decimal("banana")` raises. A stretch goal
  for later, once the manual-parsing version works: Django forms support
  building fields dynamically in `__init__`, which is the more idiomatic
  way to validate a variable set of fields — worth reading about once
  you're comfortable with static forms, not a place to start.

---

## 9. Testing

You don't need a huge suite for a weekend project, but two or three tests
will catch the mistakes that are easy to make and annoying to notice by
clicking around manually — sign flips in the balance math and rounding
that doesn't sum correctly are exactly that kind of bug.

```python
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

class BalanceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")

    def test_payment_creates_opposite_balances(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-01-01")
        alice_balances = {r["username"]: r["balance"] for r in compute_balances(self.alice)}
        bob_balances = {r["username"]: r["balance"] for r in compute_balances(self.bob)}
        self.assertEqual(alice_balances["bob"], 100)
        self.assertEqual(bob_balances["alice"], -100)

class SplitTests(TestCase):
    def test_shares_always_sum_to_total(self):
        shares = split_amount(100, {"a": Decimal(1), "b": Decimal(1), "c": Decimal(1)})
        self.assertEqual(sum(shares.values()), 100)

class AuthTests(TestCase):
    def test_balances_requires_login(self):
        response = self.client.get(reverse("balances"))
        self.assertRedirects(response, f"/login/?next={reverse('balances')}")
```

`self.client` is a fake browser Django gives every `TestCase` — it can
`.get()`, `.post()`, follow redirects, and inspect the response, all
without touching a real server or a real browser. `assertRedirects` is
worth knowing specifically: it doesn't just check the status code, it
actually follows the redirect and confirms the target page loads
correctly too.

Run the suite with:

```
uv run python manage.py test
```

Django spins up a throwaway test database for the run and tears it down
after — your real data is never touched.

---

## 10. A short checklist before you call it done

- [ ] `sender != receiver` is enforced both by the `CheckConstraint` and
      by not letting `add_record` accept a `sender` field from the client
      at all.
- [ ] Every view except `login` has `LoginRequiredMixin` (or
      `@login_required`), and it's the *first* class in the bases.
- [ ] `{{ r.note }}` and similar user-supplied text are never rendered
      with `|safe` — Django autoescapes by default, which is what stops a
      note like `<script>...</script>` from doing anything. Leave it alone.
- [ ] `group_buy`'s save is wrapped in `transaction.atomic()`.
- [ ] The Python `split_amount()` and the frontend's JS preview agree on
      every case you've tried by hand — a handful of participants with
      uneven weights is the case worth checking, not just an even split.
- [ ] `uv run python manage.py test` passes.
- [ ] `SECRET_KEY` isn't sitting in a file you're about to `git push`.

---

## Suggested build order

If you want a sequence rather than jumping around:

1. Models → `makemigrations` → `migrate` → check the migration file.
2. Admin registration → `createsuperuser` → hand-create a few test users
   and payments.
3. Login/logout wired up, `LoginRequiredMixin` on a stub `BalancesView`
   that just renders an empty list — confirm the auth redirect loop
   works before building anything behind it.
4. `compute_balances()` — write the naive version, checkpoint it in the
   shell, then the two-query version.
5. `AddRecordView` — the simplest of the three write paths, good place to
   get comfortable with `CreateView`.
6. `RecordsView` with filtering.
7. `split_amount()` as a standalone function with a test, *before* wiring
   it into `GroupBuyView` — debug the math in isolation.
8. `GroupBuyView` itself.
9. Fill in the test file from §9, then re-run the whole checklist above.

Good luck — and if you get a query returning the wrong shape or a
constraint that won't apply, paste the traceback and I'll help you read
it rather than hand you the fix outright.
