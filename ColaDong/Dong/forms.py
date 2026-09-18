from django import forms
from django.contrib.auth.models import User

from .models import Payment


class PaymentForm(forms.ModelForm):
    """Adding a payment. The sender is always the signed-in user, so it
    never appears here — the dropdown only offers the *other* users."""

    receiver = forms.ModelChoiceField(
        queryset=User.objects.all(),
        to_field_name="username",
    )

    class Meta:
        model = Payment
        fields = ["receiver", "amount", "date", "note"]

    def __init__(self, *args, sender=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sender = sender
        if sender is not None:
            self.fields["receiver"].queryset = User.objects.exclude(pk=sender.pk)

    def clean_receiver(self):
        receiver = self.cleaned_data["receiver"]
        if self._sender and receiver == self._sender:
            raise forms.ValidationError("You can't record paying yourself.")
        return receiver


class RecordFilterForm(forms.Form):
    """The four optional filters on the records page. Empty means
    'no constraint'."""

    sender = forms.ModelChoiceField(
        queryset=User.objects.all(), required=False, to_field_name="username"
    )
    receiver = forms.ModelChoiceField(
        queryset=User.objects.all(), required=False, to_field_name="username"
    )
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("date_from") and cleaned.get("date_to"):
            if cleaned["date_from"] > cleaned["date_to"]:
                raise forms.ValidationError("The start date is after the end date.")
        return cleaned


class GroupBuyForm(forms.Form):
    """The top of the split-a-purchase form. Participants and their
    multipliers are dynamic, so they're read from the request in the view."""

    payer = forms.ModelChoiceField(queryset=User.objects.all(), to_field_name="username")
    amount = forms.IntegerField(min_value=1, max_value=999_999)
    date = forms.DateField()
    note = forms.CharField(max_length=200, required=False)


def refill_dict(form, *names):
    """The templates expect a plain dict of submitted values to refill
    inputs, not a Django form object."""
    return {name: form.data.get(name, "") for name in names}
