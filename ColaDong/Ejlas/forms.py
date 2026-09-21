from django import forms

from .models import Meeting


class MeetingForm(forms.ModelForm):
    """Add a meeting. Attendees are a checkbox list of all users."""

    attendees = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Meeting
        fields = ["note", "start_time", "end_time", "place", "attendees"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        from django.contrib.auth.models import User
        super().__init__(*args, **kwargs)
        self.fields["attendees"].queryset = User.objects.order_by("username")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned
