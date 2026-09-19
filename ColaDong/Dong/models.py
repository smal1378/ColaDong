from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Payment(models.Model):
    """A single directed payment: `sender` paid `receiver` `amount` on `date`.

    Financially this means `receiver` now owes `sender` that amount, which is
    why balances are computed from these rows.
    """

    sender = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="payments_sent"
    )
    receiver = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="payments_received"
    )
    amount = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(999_999)]
    )
    date = models.DateField()
    note = models.CharField(max_length=200, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    group_purchase = models.ForeignKey(
        "GroupPurchase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shares",
    )

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(sender=models.F("receiver")),
                name="payment_sender_is_not_receiver",
            ),
        ]

    def __str__(self):
        return f"{self.sender} paid {self.receiver} ${self.amount}"


class GroupPurchase(models.Model):
    """A purchase one person paid for that is shared by several others.

    The individual shares live as Payment rows pointing back here, so this
    model is mostly a label grouping those rows.
    """

    payer = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="purchases_paid"
    )
    amount = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(999_999)]
    )
    date = models.DateField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payer} paid ${self.amount} for a group purchase"
