from django.urls import path

from . import views

app_name = "ejlas"

urlpatterns = [
    path("", views.WeekBoardView.as_view(), name="week"),
    path("add/", views.AddMeetingView.as_view(), name="add"),
]
