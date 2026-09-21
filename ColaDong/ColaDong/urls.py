from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from Dong.views import ColaLoginView


class HomePageView(TemplateView):
    """Landing page after login: lists the available apps."""

    template_name = "home.html"
    login_required = True


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomePageView.as_view(), name="home"),
    path("login/", ColaLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dong/", include("Dong.urls")),
    path("ejlas/", include("Ejlas.urls")),
    path("ip/", include("ipcalc.urls")),
]
