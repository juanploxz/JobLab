from django.conf import settings
from django.db.models import Sum
from django.shortcuts import redirect
from django.views.generic import DetailView, FormView, ListView

from organization.bootstrap import build_generation_service
from organization.domain.exceptions import GenerationError
from organization.forms import CompanyDescriptionForm
from organization.models import OrganizationalPlan


class GenerateOrganizationView(FormView):
    template_name = "organization/generate.html"
    form_class = CompanyDescriptionForm

    def form_valid(self, form):
        try:
            plan = build_generation_service().execute(form.cleaned_data["company_description"])
        except GenerationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        return redirect("organization:detail", pk=plan.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["provider_name"] = settings.AI_PROVIDER
        return context


class OrganizationalPlanDetailView(DetailView):
    model = OrganizationalPlan
    template_name = "organization/detail.html"
    context_object_name = "plan"

    def get_queryset(self):
        return super().get_queryset().select_related("request").prefetch_related(
            "units__vacancies",
            "units__children",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["root_units"] = self.object.units.filter(parent__isnull=True)
        context["department_count"] = self.object.units.count()
        context["vacancy_count"] = self.object.vacancies.count()
        context["total_positions"] = (
            self.object.vacancies.aggregate(total=Sum("available_positions"))["total"] or 0
        )
        return context


class GenerationHistoryView(ListView):
    model = OrganizationalPlan
    template_name = "organization/history.html"
    context_object_name = "plans"
    paginate_by = 12

    def get_queryset(self):
        return super().get_queryset().select_related("request")
