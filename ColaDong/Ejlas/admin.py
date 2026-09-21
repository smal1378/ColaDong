from django.contrib import admin

from .models import Meeting


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("note", "start_time", "end_time", "place")
    list_filter = ("start_time",)
    search_fields = ("note", "place")
    filter_horizontal = ("attendees",)
