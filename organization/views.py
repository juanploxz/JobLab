"""HTML views: thin adapters that call gateways (microservices) and render templates."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView, TemplateView

from organization.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)
from organization.forms import CompanyDescriptionForm, ReportRequestForm
from organization.gateways import factory
from organization.health import collect_health
from organization.presenters import build_plan_page, conversion_items, review_status_label

logger = logging.getLogger(__name__)
TASK_ID_PATTERN = re.compile(r"^[0-9a-f-]{32,36}$")
HISTORY_PAGE_SIZE = 12


def service_unavailable(request, service: str):
    return render(
        request,
        "organization/service_unavailable.html",
        {"service": service},
        status=503,
    )


class GenerateOrganizationView(FormView):
    template_name = "organization/generate.html"
    form_class = CompanyDescriptionForm

    def form_valid(self, form):
        try:
            plan_id = factory.build_plan_gateway().generate_plan(
                form.cleaned_data["company_description"]
            )
        except (GenerationError, DomainValidationError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, _("El plan se generó correctamente."))
        return redirect("organization:detail", pk=plan_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["provider_name"] = settings.AI_PROVIDER
        return context


class OrganizationalPlanDetailView(TemplateView):
    template_name = "organization/detail.html"

    def get(self, request, *args, **kwargs):
        try:
            plan = factory.build_plan_gateway().get_plan(kwargs["pk"])
        except ResourceNotFoundError as exc:
            raise Http404(exc.detail) from exc
        except ServiceUnavailableError as exc:
            return service_unavailable(request, exc.service)

        conversion = None
        if plan.vacancies:
            try:
                conversion = factory.build_integration_gateway().convert_salaries(
                    "USD", conversion_items(plan)
                )
            except ServiceUnavailableError:
                logger.info("Salary conversion unavailable for plan %s", plan.id)

        context = self.get_context_data(
            page=build_plan_page(plan, conversion),
            report_form=ReportRequestForm(),
            **kwargs,
        )
        return self.render_to_response(context)


class GenerationHistoryView(TemplateView):
    template_name = "organization/history.html"

    def get(self, request, *args, **kwargs):
        try:
            page_number = int(request.GET.get("page", 1))
        except ValueError:
            page_number = 1
        try:
            page = factory.build_plan_gateway().list_plans(page_number, HISTORY_PAGE_SIZE)
        except ResourceNotFoundError as exc:
            raise Http404(exc.detail) from exc
        except ServiceUnavailableError as exc:
            return service_unavailable(request, exc.service)
        plans = [
            {"summary": item, "review_status_label": review_status_label(item.review_status)}
            for item in page.items
        ]
        return self.render_to_response(self.get_context_data(page=page, plans=plans))


class RequestReportView(View):
    http_method_names = ["post"]

    def post(self, request, pk: int):
        form = ReportRequestForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Selecciona un formato de reporte válido."))
            return redirect("organization:detail", pk=pk)
        try:
            task = factory.build_report_gateway().request_report(pk, form.cleaned_data["format"])
        except DomainValidationError as exc:
            messages.error(request, str(exc))
            return redirect("organization:detail", pk=pk)
        except ServiceUnavailableError:
            messages.error(
                request,
                _("El servicio de reportes no está disponible. Intenta nuevamente en unos minutos."),
            )
            return redirect("organization:detail", pk=pk)
        messages.info(request, _("Tu reporte se está generando en segundo plano."))
        return redirect("organization:report-status", task_id=task["task_id"])


def _valid_task(task_id: str) -> str:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise Http404(_("No existe un reporte con ese identificador."))
    return task_id


class ReportStatusView(TemplateView):
    template_name = "organization/report_status.html"

    def get(self, request, task_id: str, *args, **kwargs):
        try:
            status = factory.build_report_gateway().report_status(_valid_task(task_id))
        except ResourceNotFoundError as exc:
            raise Http404(exc.detail) from exc
        except ServiceUnavailableError as exc:
            return service_unavailable(request, exc.service)
        finished = status.get("status") in {"SUCCESS", "FAILURE"}
        return self.render_to_response(
            self.get_context_data(task_id=task_id, report=status, finished=finished)
        )


class ReportDownloadView(View):
    def get(self, request, task_id: str):
        try:
            content, content_type, disposition = factory.build_report_gateway().download(
                _valid_task(task_id)
            )
        except ResourceNotFoundError as exc:
            raise Http404(exc.detail) from exc
        except ServiceUnavailableError as exc:
            return service_unavailable(request, exc.service)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = disposition
        return response


class AllyView(TemplateView):
    template_name = "organization/ally.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["catalog"] = factory.build_integration_gateway().ally_catalog()
        except ServiceUnavailableError as exc:
            context["catalog"] = None
            context["not_configured"] = exc.detail == "ally_not_configured"
        return context


class ActivityView(TemplateView):
    template_name = "organization/activity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["notifications"] = factory.build_report_gateway().notifications(30)
            context["available"] = True
        except ServiceUnavailableError:
            context["notifications"], context["available"] = [], False
        return context


class SystemStatusView(TemplateView):
    template_name = "organization/system_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["services"] = collect_health()
        context["plan_backend"] = factory.build_plan_gateway().name
        return context
