# Plan: Multi-app Restructuring + New Apps

This document covers the plan to restructure Cola Dong into a multi-app
project and add two new apps: **Ejlas** (meeting management) and
**IP Calculator** (stateless subnet tool).

---

## 1. Multi-app Restructuring

### Goal

Transform the single-app project into a multi-app platform with:
- A **homepage** (`/`) that lists available apps after login
- Each app under its own URL prefix with a Django namespace
- A **shared theme** (base.html + coladong.css) across all apps
- Login/logout remain at the project level

### URL Structure (after)

```
/              → HomePageView (app list, requires login)
/login/        → LoginView
/logout/       → LogoutView
/admin/        → Django admin
/dong/         → Dong app (namespaced as "dong")
/dong/balances/
/dong/records/
/dong/add-record/
/dong/group-buy/
/ejlas/        → Ejlas app (namespaced as "ejlas")
/ejlas/week/
/ejlas/add/
/ip/           → IP Calculator (namespaced as "ipcalc")
/ip/           → single page
```

### Changes

1. **`ColaDong/ColaDong/urls.py`** — Remove Dong URLs, add `include("Dong.urls")`
   at `/dong/`, `include("Ejlas.urls")` at `/ejlas/`, `include("ipcalc.urls")`
   at `/ip/`. Add homepage view at `/`.

2. **`Dong/urls.py`** (new) — `app_name = "dong"`, contains the four Dong URLs
   (balances, records, add_record, group_buy) + the CSV export.

3. **`Dong/views.py`** — Update `reverse_lazy("balances")` →
   `reverse_lazy("dong:balances")`, and any other URL reverses.

4. **All Dong templates** — Update `{% url 'balances' %}` →
   `{% url 'dong:balances' %}`, etc.

5. **`templates/home.html`** (new) — App list page. Shows cards/links for
   Dong, Ejlas, IP Calculator. Extends base.html.

6. **`templates/base.html`** — Generalize the nav. The masthead shows:
   - Brand ("Cola Dong")
   - "Home" link
   - `{% block app_nav %}{% endblock %}` — each app fills with its own links
   - Session (username + logout)

7. **`settings.py`** — Add `"Ejlas"` and `"ipcalc"` to `INSTALLED_APPS`.

8. **CSS** — Stays in `Dong/static/css/coladong.css`. Already accessible to
   all apps via Django's staticfiles framework (`{% static "css/coladong.css" %}`).
   No move needed.

### Homepage View

Simple `TemplateView` (login required) that renders `home.html` with a list
of apps: name, description, URL. No model, no DB query.

---

## 2. Ejlas App (Meeting Management)

### Purpose

Manage meeting times, places, and people for the friend group. Weekly board
view (Saturday–Thursday, since Iran's work week starts Saturday and Friday
is the only weekend day).

### Models

```python
class Meeting(models.Model):
    note      = CharField(max_length=200, blank=True)
    start_time = DateTimeField()
    end_time   = DateTimeField()
    place      = CharField(max_length=200, blank=True)  # optional
    attendees  = ManyToManyField(User, related_name="meetings")
    created_at = DateTimeField(auto_now_add=True)

    # CheckConstraint: end_time > start_time
```

One model. `place` is a nullable string (not a separate model) — for a small
friend group, free-text place names are sufficient and a Place table adds
maintenance for no benefit at this scale.

### Views

| View | URL | Purpose |
|------|-----|---------|
| `WeekBoardView` | `/ejlas/week/` | Show the current (or selected) week's meetings in a Sat–Thu grid |
| `AddMeetingView` | `/ejlas/add/` | Form to create a meeting; runs conflict checks on save |

#### WeekBoardView

- Default: current week (Sat–Thu). Optional `?week=2025-W38` or
  `?date=YYYY-MM-DD` param to view another week.
- Context: 6 day columns (Sat, Sun, Mon, Tue, Wed, Thu), each listing its
  meetings sorted by `start_time`. Each meeting shows time range, note,
  place, attendees.
- Below the board: a **Conflicts** section listing all conflicts for that
  week (see detection logic below).

#### AddMeetingView

- Form fields: note, start_time, end_time, place, attendees (checkbox list
  of all users).
- On valid POST: create the Meeting, run conflict detection against
  existing meetings that overlap in time. If conflicts exist, show a
  warning (non-blocking — the meeting is still saved, but the user sees
  what it conflicts with).
- Redirect to week board with a flash message.

### Conflict Detection

Two meetings **overlap in time** if:
```
a.start_time < b.end_time AND b.start_time < a.end_time
```

On top of time overlap:
- **Person conflict**: they share ≥ 1 attendee.
- **Place conflict**: they have the same non-empty `place` string
  (case-insensitive comparison).

A meeting can have both types of conflict simultaneously. Conflicts are
computed in a service function (`services.py`) for testability:

```python
def find_conflicts(meeting, existing_meetings):
    """Return list of dicts describing conflicts between `meeting` and
    each overlapping existing meeting."""
```

### Templates

- `ejlas/week.html` — extends base.html, fills `app_nav` with Ejlas links
- `ejlas/add_meeting.html` — extends base.html, the meeting form

### CSS

Reuses the shared coladong.css. A few Ejlas-specific classes for the week
grid (day columns, meeting cards, conflict highlighting) will be appended
to the stylesheet or in a small `<style>` block if minimal.

### Tests

- Model constraint (end > start)
- Conflict detection: person overlap, place overlap, no false positives
- Week board: correct meetings shown for a given week
- Add meeting: valid save, conflict warning shown

---

## 3. IP Calculator App

### Purpose

Stateless, single-page subnet calculator. No database, no models, no
auth requirement (or login required for consistency — TBD, leaning toward
login required to keep the app behind auth).

### Input

User enters a CIDR notation string (e.g., `192.168.0.0/16`) or separately:
- Network address (4 octets)
- Prefix length (8–32)

### Output (computed in real-time via JavaScript)

- Network address
- Broadcast address
- First usable host
- Last usable host
- Total number of addresses
- Number of usable hosts
- Subnet mask (dotted quad)
- Wildcard mask
- Whether it's a private/reserved range

### Implementation

- Single view: `TemplateView` rendering `ipcalc/calculator.html`
- All computation in client-side JavaScript (no server round-trip)
- The JS listens to input events and recomputes on every keystroke
- No Django models, no forms, no POST

### Files

- `ipcalc/` app: `views.py` (one TemplateView), `urls.py`, `apps.py`
- `templates/ipcalc/calculator.html` — the single page with inline JS
  (or a static `.js` file to be CSP-safe)
- No migrations (no models)

### Priority

Low. Implement after the restructuring and Ejlas are complete and committed.

---

## 4. Implementation Order

1. Structural changes (homepage, URL reorg, base.html, Dong namespacing)
2. Test + commit
3. Ejlas app (models, forms, views, templates, tests)
4. Test + commit
5. IP Calculator (template + JS)
6. Test + commit
7. Update all .md documentation
8. Final test + commit

---

## 5. Open Questions

- **IP calc auth**: should it require login like the other apps, or be
  publicly accessible (it's a stateless tool)? Leaning: require login for
  consistency, since the whole site is behind auth.
- **Ejlas week navigation**: prev/next week buttons, or a date picker?
  Leaning: simple prev/next arrows + "This week" link.
- **Meeting editing/deletion**: out of scope for now (consistent with Dong
  which also has no edit/delete).
