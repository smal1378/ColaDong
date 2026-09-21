from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class CalculatorView(LoginRequiredMixin, TemplateView):
    """Single-page subnet calculator. All computation happens client-side in JS."""

    template_name = "ipcalc/calculator.html"
