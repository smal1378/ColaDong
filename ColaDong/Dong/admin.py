from django.contrib import admin

from .models import GroupPurchase, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "sender", "receiver", "amount", "group_purchase")
    list_filter = ("date",)
    search_fields = ("note",)
    autocomplete_fields = ("sender", "receiver")


@admin.register(GroupPurchase)
class GroupPurchaseAdmin(admin.ModelAdmin):
    list_display = ("date", "payer", "amount", "note", "created_at")
    list_filter = ("date",)
    search_fields = ("note",)
    autocomplete_fields = ("payer",)
