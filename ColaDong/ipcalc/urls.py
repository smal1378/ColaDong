from django.urls import path

from . import views

app_name = "ipcalc"

urlpatterns = [
    path("", views.CalculatorView.as_view(), name="calculator"),
]
