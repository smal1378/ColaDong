"""Business logic for Cola Dong, kept out of the views so it can be
tested directly.

Sign convention: a balance is signed from the point of view of the user
it's computed for. Positive means the other person owes them money;
negative means they owe the other person.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum, Count

from .models import GroupPurchase, Payment


def compute_balances(user):
    """Net position between `user` and every other user.

    Returns one row per other user, ordered by username, including users
    with a zero balance.
    """
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
    for row in outgoing:  # they received money, so they owe the user
        net[row["receiver__username"]] = net.get(row["receiver__username"], 0) + row["total"]
    for row in incoming:  # the user received money, so the user owes them
        net[row["sender__username"]] = net.get(row["sender__username"], 0) - row["total"]

    rows = []
    for other in User.objects.exclude(pk=user.pk).order_by("username"):
        rows.append({
            "username": other.username,
            "name": other.first_name,
            "balance": net.get(other.username, 0),
        })
    return rows


def split_amount(total, weights):
    """Split `total` whole dollars across `weights` (a list of Decimals) so
    the parts add back up to exactly `total`, using largest-remainder
    rounding — the same rule the group-buy page's live preview uses, so the
    preview always matches what gets saved.
    """
    weights = [Decimal(str(w)) for w in weights]
    sum_w = sum(weights)
    if sum_w <= 0:
        raise ValueError("Shares must add up to a positive total.")

    exact = [Decimal(total) * w / sum_w for w in weights]
    parts = [int(e) for e in exact]  # floor, all values are positive
    left = total - sum(parts)

    order = sorted(range(len(weights)), key=lambda i: exact[i] - parts[i], reverse=True)
    for i in range(left):
        parts[order[i % len(order)]] += 1
    return parts


def settle_up():
    """Suggest the minimal set of transfers that would settle all debts
    in the group.

    Returns a list of dicts: {"from": username, "to": username, "amount": int}
    """
    balances = {}
    for u in User.objects.all():
        sent = Payment.objects.filter(sender=u).aggregate(t=Sum("amount"))["t"] or 0
        received = Payment.objects.filter(receiver=u).aggregate(t=Sum("amount"))["t"] or 0
        balances[u.username] = sent - received

    creditors = {u: b for u, b in balances.items() if b > 0}
    debtors = {u: -b for u, b in balances.items() if b < 0}

    transfers = []
    while debtors and creditors:
        debtor = max(debtors, key=debtors.get)
        creditor = max(creditors, key=creditors.get)
        amount = min(debtors[debtor], creditors[creditor])
        transfers.append({"from": debtor, "to": creditor, "amount": amount})
        debtors[debtor] -= amount
        creditors[creditor] -= amount
        if debtors[debtor] == 0:
            del debtors[debtor]
        if creditors[creditor] == 0:
            del creditors[creditor]
    return transfers


def monthly_stats(user):
    """Total sent and received per month for `user`, most recent first."""
    from django.db.models.functions import TruncMonth

    sent = (
        Payment.objects.filter(sender=user)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"), count=Count("id"))
    )
    received = (
        Payment.objects.filter(receiver=user)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"), count=Count("id"))
    )

    months = {}
    for row in sent:
        m = row["month"]
        if m is None:
            continue
        months.setdefault(m, {"sent": 0, "received": 0, "sent_count": 0, "received_count": 0})
        months[m]["sent"] = row["total"] or 0
        months[m]["sent_count"] = row["count"] or 0
    for row in received:
        m = row["month"]
        if m is None:
            continue
        months.setdefault(m, {"sent": 0, "received": 0, "sent_count": 0, "received_count": 0})
        months[m]["received"] = row["total"] or 0
        months[m]["received_count"] = row["count"] or 0

    return [
        {"month": m, "sent": v["sent"], "received": v["received"], "sent_count": v["sent_count"], "received_count": v["received_count"]}
        for m, v in sorted(months.items(), reverse=True)
    ]
