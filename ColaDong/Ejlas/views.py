from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from .forms import MeetingForm
from .models import Meeting
from .services import find_conflicts, find_week_conflicts


def week_start(d):
    """Return the Saturday on or before date `d` (Iran week starts Saturday)."""
    # weekday(): Mon=0 ... Sun=6. Saturday=5.
    offset = (d.weekday() - 5) % 7
    return d - timedelta(days=offset)


class WeekBoardView(LoginRequiredMixin, TemplateView):
    """The weekly meeting board: six day columns (Sat–Thu), meetings listed
    per day, plus a conflicts section below."""

    template_name = "ejlas/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ref = date.today()
        if "date" in self.request.GET:
            try:
                ref = date.fromisoformat(self.request.GET["date"])
            except ValueError:
                pass

        start = week_start(ref)
        days = []
        for i in range(6):  # Sat, Sun, Mon, Tue, Wed, Thu
            d = start + timedelta(days=i)
            day_meetings = (
                Meeting.objects.filter(start_time__date=d)
                .prefetch_related("attendees")
                .order_by("start_time")
            )
            days.append({"name": d.strftime("%A"), "date": d, "meetings": list(day_meetings)})

        all_week = list(
            Meeting.objects.filter(start_time__date__range=(start, start + timedelta(days=5)))
            .prefetch_related("attendees")
            .order_by("start_time")
        )
        conflicts = find_week_conflicts(all_week)

        prev_start = start - timedelta(days=7)
        next_start = start + timedelta(days=7)

        context.update({
            "days": days,
            "conflicts": conflicts,
            "week_start": start,
            "prev_date": (prev_start + timedelta(days=3)).isoformat(),
            "next_date": (next_start + timedelta(days=3)).isoformat(),
            "this_week_date": week_start(date.today()).isoformat(),
        })
        return context


class AddMeetingView(LoginRequiredMixin, View):
    """Create a meeting. On save, checks for conflicts and warns (non-blocking)."""

    template_name = "ejlas/add_meeting.html"

    def get(self, request):
        return self._render(request)

    def post(self, request):
        form = MeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            existing = Meeting.objects.exclude(pk=meeting.pk).prefetch_related("attendees")
            conflicts = find_conflicts(meeting, existing)

            meeting.save()
            meeting.attendees.set(form.cleaned_data.get("attendees") or [])

            if conflicts:
                names = ", ".join(f"{c['meeting']}" for c in conflicts)
                messages.warning(request, f"Saved, but it conflicts with: {names}")
            else:
                messages.success(request, f"Meeting saved: {meeting}")
            return redirect("ejlas:week")
        return self._render(request, form=form)

    def _render(self, request, form=None):
        context = {"form": form}
        return render(request, self.template_name, context)
