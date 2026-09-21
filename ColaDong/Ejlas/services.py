"""Conflict detection for the Ejlas meeting planner."""


def times_overlap(a_start, a_end, b_start, b_end):
    """True if two time intervals overlap (exclusive boundaries)."""
    return a_start < b_end and b_start < a_end


def find_conflicts(meeting, existing_meetings):
    """Check `meeting` against a list of saved meetings.

    Returns a list of dicts, one per conflicting meeting:
    {"meeting": Meeting, "types": ["person", "place"]}
    """
    conflicts = []
    for other in existing_meetings:
        if not times_overlap(
            meeting.start_time, meeting.end_time,
            other.start_time, other.end_time,
        ):
            continue

        types = []

        if meeting.place and other.place and \
                meeting.place.strip().lower() == other.place.strip().lower():
            types.append("place")

        meeting_attendees = set(meeting.attendees.all().values_list("pk", flat=True))
        other_attendees = set(other.attendees.all().values_list("pk", flat=True))
        if meeting_attendees & other_attendees:
            types.append("person")

        if types:
            conflicts.append({"meeting": other, "types": types})

    return conflicts


def find_week_conflicts(meetings):
    """Find all conflicts within a list of meetings (for the week board).

    Returns a list of dicts:
    {"a": Meeting, "b": Meeting, "types": ["person", "place"]}
    """
    conflicts = []
    for i in range(len(meetings)):
        for j in range(i + 1, len(meetings)):
            a, b = meetings[i], meetings[j]
            if not times_overlap(a.start_time, a.end_time, b.start_time, b.end_time):
                continue

            types = []
            if a.place and b.place and \
                    a.place.strip().lower() == b.place.strip().lower():
                types.append("place")
            a_att = set(a.attendees.all().values_list("pk", flat=True))
            b_att = set(b.attendees.all().values_list("pk", flat=True))
            if a_att & b_att:
                types.append("person")

            if types:
                conflicts.append({"a": a, "b": b, "types": types})

    return conflicts
