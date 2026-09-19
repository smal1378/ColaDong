from datetime import date
from decimal import Decimal, InvalidOperation

import csv

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView

from .forms import GroupBuyForm, PaymentForm, RecordFilterForm, flatten_errors, refill_dict
from .models import GroupPurchase, Payment
from .services import compute_balances, monthly_stats, settle_up, split_amount


def client_ip(request):
    """Best-effort client IP, respecting the X-Forwarded-For header."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
        context["settle_up"] = settle_up(self.request.user)
        context["monthly"] = monthly_stats(self.request.user)
        return context


class RecordsView(LoginRequiredMixin, TemplateView):
    """The payment list. Filters use GET so filtered views are bookmarkable."""

    template_name = "records.html"
    filter_names = ("sender", "receiver", "date_from", "date_to")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = RecordFilterForm(self.request.GET or None)
        qs = Payment.objects.select_related("sender", "receiver")
        if form.is_valid():
            data = form.cleaned_data
            if data["sender"]:
                qs = qs.filter(sender=data["sender"])
            if data["receiver"]:
                qs = qs.filter(receiver=data["receiver"])
            if data["date_from"]:
                qs = qs.filter(date__gte=data["date_from"])
            if data["date_to"]:
                qs = qs.filter(date__lte=data["date_to"])
        qs = qs.order_by("-date", "-id")
        paginator = Paginator(qs, 25)
        page_number = self.request.GET.get("page", 1)
        page = paginator.get_page(page_number)
        params = self.request.GET.copy()
        params.pop("page", None)
        context["users"] = User.objects.order_by("username")
        context["page"] = page
        context["filters"] = {name: self.request.GET.get(name, "") for name in self.filter_names}
        context["total_amount"] = qs.aggregate(total=Sum("amount"))["total"] or 0
        context["query_string"] = params.urlencode()
        return context


class RecordsCsvView(LoginRequiredMixin, View):
    """Download the (filtered) records as a CSV file."""

    filter_names = ("sender", "receiver", "date_from", "date_to")

    def get(self, request):
        form = RecordFilterForm(request.GET or None)
        qs = Payment.objects.select_related("sender", "receiver").order_by("-date", "-id")
        if form.is_valid():
            data = form.cleaned_data
            if data["sender"]:
                qs = qs.filter(sender=data["sender"])
            if data["receiver"]:
                qs = qs.filter(receiver=data["receiver"])
            if data["date_from"]:
                qs = qs.filter(date__gte=data["date_from"])
            if data["date_to"]:
                qs = qs.filter(date__lte=data["date_to"])

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="coladong-payments.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Paid by", "Paid to", "Amount", "Note", "IP"])
        for r in qs:
            writer.writerow([r.date.isoformat(), r.sender.username, r.receiver.username, r.amount, r.note, r.ip_address or ""])
        return response


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
            all_weights = [w for _, w in pairs]
            parts = split_amount(form.cleaned_data["amount"], all_weights)
        except ValueError:
            return "The shares don't add up."

        user_by_name = {u.username: u for u in User.objects.all()}
        note = form.cleaned_data["note"]
        ip = client_ip(request)
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
                    ip_address=ip,
                    group_purchase=purchase,
                )
                for (n, _), part in zip(pairs, parts)
                if n != payer.username
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
        if form.cleaned_data.get("direction") == "borrowed":
            form.instance.sender = form.cleaned_data["receiver"]
            form.instance.receiver = self.request.user
        else:
            form.instance.sender = self.request.user
        form.instance.ip_address = client_ip(self.request)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["users"] = User.objects.exclude(pk=self.request.user.pk).order_by("username")
        context["today"] = date.today().isoformat()
        form = kwargs.get("form")
        if form is not None:
            context["form"] = refill_dict(form, "direction", "receiver", "amount", "date", "note")
        return context
