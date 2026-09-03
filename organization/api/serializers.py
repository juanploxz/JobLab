"""DRF serializers limited to HTTP input/output representation."""

from rest_framework import serializers


class GeneratePlanInputSerializer(serializers.Serializer):
    company_description = serializers.CharField(allow_blank=True, trim_whitespace=False)


class CreateVacancyInputSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()
    name = serializers.CharField(allow_blank=True, trim_whitespace=False)
    available_positions = serializers.IntegerField()
    salary_min = serializers.DecimalField(max_digits=14, decimal_places=2)
    salary_max = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(allow_blank=True, max_length=3)
    salary_period = serializers.CharField(allow_blank=True, max_length=10)
    description = serializers.CharField(allow_blank=True, trim_whitespace=False)
    required_knowledge = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        allow_empty=True,
    )
    reports_to = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="",
        trim_whitespace=False,
    )


class PlanMetricsOutputSerializer(serializers.Serializer):
    department_count = serializers.IntegerField()
    vacancy_count = serializers.IntegerField()
    total_positions = serializers.IntegerField()


class OrganizationalUnitOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    parent_id = serializers.IntegerField(allow_null=True)


class VacancyOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    department_id = serializers.IntegerField()
    department_name = serializers.CharField()
    name = serializers.CharField()
    available_positions = serializers.IntegerField()
    salary_min = serializers.DecimalField(max_digits=14, decimal_places=2)
    salary_max = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    salary_period = serializers.CharField()
    description = serializers.CharField()
    required_knowledge = serializers.ListField(child=serializers.CharField())
    reports_to = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class PlanSummaryOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_name = serializers.CharField()
    review_status = serializers.CharField()
    generation_status = serializers.CharField(source="request.status")
    provider_name = serializers.CharField(source="request.provider_name")
    created_at = serializers.DateTimeField()


class PlanDetailOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    request_id = serializers.IntegerField()
    company_name = serializers.CharField()
    company_summary = serializers.CharField()
    assumptions = serializers.ListField(child=serializers.CharField())
    review_status = serializers.CharField()
    generation_status = serializers.CharField()
    provider_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    metrics = PlanMetricsOutputSerializer()
    units = OrganizationalUnitOutputSerializer(many=True)
    vacancies = VacancyOutputSerializer(many=True)


class APIErrorDetailOutputSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.JSONField(required=False)


class APIErrorOutputSerializer(serializers.Serializer):
    error = APIErrorDetailOutputSerializer()
