from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView


class FlatErrorMixin:
    """Flatten Django form errors into the single `error` string the templates expect."""

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["error"] = " ".join(form.non_field_errors())
        return self.render_to_response(context)


class ColaLoginView(FlatErrorMixin, LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form")
        if form is not None:
            context["username"] = form.data.get("username", "")
        return context


class BalancesView(TemplateView):
    template_name = "balances.html"


class RecordsView(TemplateView):
    template_name = "records.html"
