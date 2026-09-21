from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


def aware(*args):
    return timezone.make_aware(datetime(*args))

from .models import Meeting
from .services import find_conflicts, find_week_conflicts, times_overlap


class TimesOverlapTests(TestCase):
    def test_overlapping(self):
        a_start = aware(2026, 1, 1, 10, 0)
        a_end = aware(2026, 1, 1, 11, 0)
        b_start = aware(2026, 1, 1, 10, 30)
        b_end = aware(2026, 1, 1, 11, 30)
        self.assertTrue(times_overlap(a_start, a_end, b_start, b_end))

    def test_non_overlapping(self):
        a_start = aware(2026, 1, 1, 10, 0)
        a_end = aware(2026, 1, 1, 11, 0)
        b_start = aware(2026, 1, 1, 11, 0)
        b_end = aware(2026, 1, 1, 12, 0)
        self.assertFalse(times_overlap(a_start, a_end, b_start, b_end))


class FindConflictsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")

    def test_person_conflict(self):
        m1 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 10, 0),
            end_time=aware(2026, 1, 1, 11, 0),
        )
        m1.attendees.add(self.alice)

        m2 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 10, 30),
            end_time=aware(2026, 1, 1, 11, 30),
        )
        m2.attendees.add(self.alice)

        conflicts = find_conflicts(m1, Meeting.objects.exclude(pk=m1.pk).prefetch_related("attendees"))
        self.assertEqual(len(conflicts), 1)
        self.assertIn("person", conflicts[0]["types"])

    def test_place_conflict(self):
        m1 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 10, 0),
            end_time=aware(2026, 1, 1, 11, 0),
            place="Office A",
        )
        m2 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 10, 30),
            end_time=aware(2026, 1, 1, 11, 30),
            place="office a",
        )

        conflicts = find_conflicts(m1, Meeting.objects.exclude(pk=m1.pk).prefetch_related("attendees"))
        self.assertEqual(len(conflicts), 1)
        self.assertIn("place", conflicts[0]["types"])

    def test_no_conflict(self):
        m1 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 10, 0),
            end_time=aware(2026, 1, 1, 11, 0),
        )
        m2 = Meeting.objects.create(
            start_time=aware(2026, 1, 1, 12, 0),
            end_time=aware(2026, 1, 1, 13, 0),
        )

        conflicts = find_conflicts(m1, Meeting.objects.exclude(pk=m1.pk).prefetch_related("attendees"))
        self.assertEqual(conflicts, [])


class WeekBoardTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.client.login(username="alice", password="pw")

    def test_week_board_renders(self):
        response = self.client.get(reverse("ejlas:week"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Week board")

    def test_add_meeting_page_renders(self):
        response = self.client.get(reverse("ejlas:add"))
        self.assertEqual(response.status_code, 200)

    def test_add_meeting_creates(self):
        response = self.client.post(reverse("ejlas:add"), {
            "note": "Test meeting",
            "start_time": "2026-09-22T10:00",
            "end_time": "2026-09-22T11:00",
            "place": "Room 1",
            "attendees": [self.alice.pk],
        })
        self.assertRedirects(response, reverse("ejlas:week"))
        self.assertEqual(Meeting.objects.count(), 1)
        self.assertEqual(Meeting.objects.first().note, "Test meeting")

    def test_end_before_start_rejected(self):
        response = self.client.post(reverse("ejlas:add"), {
            "note": "Bad meeting",
            "start_time": "2026-09-22T11:00",
            "end_time": "2026-09-22T10:00",
            "place": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Meeting.objects.count(), 0)
