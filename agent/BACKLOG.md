# Backlog

Known work that is deliberately not active.

- No editing or deleting of Dong records — spec only asked for add/view.
- No REST API — server-rendered templates are preferred for current scope.
- Ejlas has no meeting editing/deletion and no separate `Place` model.
- `HomePageView.login_required = True` is a no-op on `TemplateView`.
- `AdminUpdateView` has no URL route; its template override is outside
  configured template dirs.
- `RETURN.txt` remains deleted; user objected only to deleting planning
  files. Decide whether to restore it.
- `group_buy.html` has an inline script; if `SECURE_CSP` is enabled, move
  that script into a static JS file.
- Reconsider the trust model only if the friend-group honor system changes:
  `add_record` never accepts sender, while `group_buy` payer is selectable.
- Deployment scripts live in `deploy/`; verify they still match the current
  repo before deploying.
