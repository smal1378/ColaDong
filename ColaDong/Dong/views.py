from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView

from .forms import GroupBuyForm, PaymentForm, RecordFilterForm, flatten_errors, refill_dict
from .models import GroupPurchase, Payment
from .services import compute_balances, split_amount


class FlatErrorMixin:
    """Flatten Django form errors into the single `error` string the templates expect."""

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["error"] = flatten_errors(form)
        return self.render_to_response(context)


class ColaLoginView(FlatErrorMixin, LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form")
        if form is not None:
            context["username"] = form.data.get("username", "")
        return context


class BalancesView(LoginRequiredMixin, TemplateView):
    template_name = "balances.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        balances = compute_balances(self.request.user)
        context["balances"] = balances
        context["net_balance"] = sum(row["balance"] for row in balances)
        return context


class RecordsView(LoginRequiredMixin, View):
    """The payment list. Filters POST to the same URL; a bare GET shows
    everything."""

    template_name = "records.html"
    filter_names = ("sender", "receiver", "date_from", "date_to")

    def get(self, request):
        return self._render(request)

    def post(self, request):
        form = RecordFilterForm(request.POST)
        if not form.is_valid():
            messages.error(request, flatten_errors(form))
        filters = {name: request.POST.get(name, "") for name in self.filter_names}
        return self._render(request, form=form, filters=filters)

    def _render(self, request, form=None, filters=None):
        qs = Payment.objects.select_related("sender", "receiver")
        if form is not None and form.is_valid():
            data = form.cleaned_data
            if data["sender"]:
                qs = qs.filter(sender=data["sender"])
            if data["receiver"]:
                qs = qs.filter(receiver=data["receiver"])
            if data["date_from"]:
                qs = qs.filter(date__gte=data["date_from"])
            if data["date_to"]:
                qs = qs.filter(date__lte=data["date_to"])

        context = {
            "users": User.objects.order_by("username"),
            "records": qs,
            "filters": filters or {},
            "total_amount": qs.aggregate(total=Sum("amount"))["total"] or 0,
        }
        return render(request, self.template_name, context)


class GroupBuyView(LoginRequiredMixin, View):
    """One person paid, several share the cost. Saves a GroupPurchase plus
    one Payment per sharer, all in a single transaction."""

    template_name = "group_buy.html"

    def get(self, request):
        return self._render(request)

    def post(self, request):
        form = GroupBuyForm(request.POST)
        names = list(dict.fromkeys(request.POST.getlist("participants")))
        weights = {n: request.POST.get(f"weight_{n}") or "1" for n in names}

        if not form.is_valid():
            error = flatten_errors(form)
        elif not names:
            error = "Tick at least one person to share the cost with."
        else:
            error = self._save_split(request, form, names, weights)
        if error is None:
            return redirect("balances")
        return self._render(request, form=form, names=names, weights=weights, error=error)

    def _save_split(self, request, form, names, weights):
        """Validates the dynamic fields and saves the purchase. Returns an
        error string, or None on success."""
        try:
            pairs = [(n, Decimal(weights[n])) for n in names]
        except (InvalidOperation, KeyError):
            return "Share multipliers must be numbers."
        if any(w <= 0 for _, w in pairs):
            return "Share multipliers must be greater than zero."

        payer = form.cleaned_data["payer"]
        others = [(n, w) for n, w in pairs if n != payer.username]
        if not others:
            return "Pick at least one other person to share with."

        try:
            parts = split_amount(form.cleaned_data["amount"], [w for _, w in others])
        except ValueError:
            return "The shares don't add up."

        user_by_name = {u.username: u for u in User.objects.all()}
        note = form.cleaned_data["note"]
        with transaction.atomic():
            purchase = GroupPurchase(
                payer=payer,
                amount=form.cleaned_data["amount"],
                date=form.cleaned_data["date"],
                note=note,
            )
            purchase.save()
            Payment.objects.bulk_create(
                Payment(
                    sender=payer,
                    receiver=user_by_name[n],
                    amount=part,
                    date=purchase.date,
                    note=note,
                    group_purchase=purchase,
                )
                for (n, _), part in zip(others, parts)
            )
        messages.success(
            request,
            f"Saved: {payer.username} paid ${purchase.amount} — "
            f"{len(others)} friends owe their share.",
        )
        return None

    def _render(self, request, form=None, names=None, weights=None, error=None):
        rows = []
        for u in User.objects.order_by("username"):
            row = {"username": u.username, "name": u.first_name}
            if names is not None:
                row["selected"] = u.username in names
                row["weight"] = weights.get(u.username, "1")
            rows.append(row)
        context = {"users": rows, "today": date.today().isoformat(), "error": error}
        if form is not None:
            context["form"] = {n: form.data.get(n, "") for n in ("payer", "amount", "date", "note")}
        return render(request, self.template_name, context)


class AddRecordView(FlatErrorMixin, LoginRequiredMixin, CreateView):
    """Record a payment the signed-in user made. The sender is always the
    signed-in user, set server-side — never read from the request."""

    model = Payment
    form_class = PaymentForm
    template_name = "add_record.html"
    success_url = reverse_lazy("balances")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["sender"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["users"] = User.objects.exclude(pk=self.request.user.pk).order_by("username")
        context["today"] = date.today().isoformat()
        form = kwargs.get("form")
        if form is not None:
            context["form"] = refill_dict(form, "receiver", "amount", "date", "note")
        return context
