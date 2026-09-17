"""
URL configuration for ColaDong project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

import Dong.views as views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="balances")),
    path("admin/", admin.site.urls),
    path("login/", views.ColaLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("balances/", views.BalancesView.as_view(), name="balances"),
    path("records/", views.RecordsView.as_view(), name="records"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
