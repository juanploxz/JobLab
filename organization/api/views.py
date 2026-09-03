"""Thin APIViews: deserialize, invoke one use case, and serialize its result."""

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from organization.api.pagination import PlanPageNumberPagination
from organization.api.responses import (
    application_error_response,
    child_location,
    error_response,
    serializer_error_response,
)
from organization.api.serializers import (
    CreateVacancyInputSerializer,
    GeneratePlanInputSerializer,
    PlanDetailOutputSerializer,
    PlanSummaryOutputSerializer,
    VacancyOutputSerializer,
)
from organization.bootstrap import build_generation_service
from organization.domain.exceptions import (
    DomainValidationError,
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from organization.dtos import CreateVacancyCommand
from organization.services import (
    CreateVacancyService,
    GetOrganizationalPlanService,
    GetVacancyService,
    ListOrganizationalPlansService,
)

APPLICATION_EXCEPTIONS = (
    DomainValidationError,
    GenerationError,
    ResourceConflictError,
    ResourceNotFoundError,
    ImproperlyConfigured,
)


class UniformErrorAPIView(APIView):
    """Keep framework-generated failures inside the public error contract."""

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if isinstance(response.data, dict) and "error" in response.data:
            return response

        response_data = response.data
        detail = "La solicitud no pudo ser procesada."
        fields = None
        if isinstance(response_data, dict):
            detail_value = response_data.get("detail")
            if detail_value is not None:
                detail = str(detail_value)
            else:
                fields = response_data
        elif response_data:
            fields = response_data

        return error_response(
            code=str(getattr(exc, "default_code", "api_error")),
            detail=detail,
            fields=fields,
            status_code=response.status_code,
        )


class PlanCollectionAPIView(UniformErrorAPIView):
    """List plans or generate a complete organizational plan."""

    generation_service_factory = staticmethod(build_generation_service)
    list_service_factory = staticmethod(ListOrganizationalPlansService)
    detail_service_factory = staticmethod(GetOrganizationalPlanService)
    pagination_class = PlanPageNumberPagination

    def get(self, request):
        plans = self.list_service_factory().execute()
        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(plans, request, view=self)
        except NotFound as exc:
            return error_response(
                code="page_not_found",
                detail=str(exc.detail),
                status_code=status.HTTP_404_NOT_FOUND,
            )
        output = PlanSummaryOutputSerializer(page, many=True)
        return paginator.get_paginated_response(output.data)

    def post(self, request):
        input_serializer = GeneratePlanInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return serializer_error_response(input_serializer.errors)

        try:
            plan = self.generation_service_factory().execute(
                input_serializer.validated_data["company_description"]
            )
            result = self.detail_service_factory().execute(plan.pk)
        except APPLICATION_EXCEPTIONS as exc:
            return application_error_response(exc)

        return Response(
            PlanDetailOutputSerializer(result).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": child_location(request, result.id)},
        )


class PlanDetailAPIView(UniformErrorAPIView):
    """Return one complete organizational plan read model."""

    detail_service_factory = staticmethod(GetOrganizationalPlanService)

    def get(self, request, pk: int):
        try:
            result = self.detail_service_factory().execute(pk)
        except ResourceNotFoundError as exc:
            return application_error_response(exc)
        return Response(PlanDetailOutputSerializer(result).data)


class PlanVacancyCollectionAPIView(UniformErrorAPIView):
    """Create a vacancy inside an existing plan."""

    vacancy_service_factory = staticmethod(CreateVacancyService)

    def post(self, request, pk: int):
        input_serializer = CreateVacancyInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return serializer_error_response(input_serializer.errors)

        data = input_serializer.validated_data
        command = CreateVacancyCommand(
            department_id=data["department_id"],
            name=data["name"],
            available_positions=data["available_positions"],
            salary_min=data["salary_min"],
            salary_max=data["salary_max"],
            currency=data["currency"],
            salary_period=data["salary_period"],
            description=data["description"],
            required_knowledge=tuple(data["required_knowledge"]),
            reports_to=data["reports_to"] or "",
        )
        try:
            result = self.vacancy_service_factory().execute(pk, command)
        except (DomainValidationError, ResourceConflictError, ResourceNotFoundError) as exc:
            return application_error_response(exc)

        return Response(
            VacancyOutputSerializer(result).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": child_location(request, result.id)},
        )


class PlanVacancyDetailAPIView(UniformErrorAPIView):
    """Return one vacancy scoped to its organizational plan."""

    vacancy_service_factory = staticmethod(GetVacancyService)

    def get(self, request, pk: int, vacancy_pk: int):
        try:
            result = self.vacancy_service_factory().execute(pk, vacancy_pk)
        except ResourceNotFoundError as exc:
            return application_error_response(exc)
        return Response(VacancyOutputSerializer(result).data)
