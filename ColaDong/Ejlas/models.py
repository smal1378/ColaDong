from django.contrib.auth.models import User
from django.db import models


class Meeting(models.Model):
    """A scheduled meeting with a time window, optional place, and attendees."""

    note = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    place = models.CharField(max_length=200, blank=True)
    attendees = models.ManyToManyField(User, related_name="meetings", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="meeting_end_after_start",
            ),
        ]

    def __str__(self):
        label = self.note or "Meeting"
        return f"{label} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    @property
    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() // 60)
