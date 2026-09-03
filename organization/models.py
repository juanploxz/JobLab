from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models.functions import Lower

from organization.domain.validators import (
    MAX_AVAILABLE_POSITIONS,
    MAX_COMPANY_SUMMARY_LENGTH,
    MAX_UNIT_DESCRIPTION_LENGTH,
    MAX_VACANCY_DESCRIPTION_LENGTH,
    MIN_AVAILABLE_POSITIONS,
    MIN_COMPANY_NAME_LENGTH,
    MIN_COMPANY_SUMMARY_LENGTH,
    MIN_UNIT_DESCRIPTION_LENGTH,
    MIN_UNIT_NAME_LENGTH,
    MIN_VACANCY_DESCRIPTION_LENGTH,
    MIN_VACANCY_NAME_LENGTH,
    validate_assumptions,
    validate_company_description_field,
    validate_required_knowledge,
)


class OrganizationGenerationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        PROCESSING = "PROCESSING", "Procesando"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallida"

    company_description = models.TextField(
        max_length=5000,
        validators=[validate_company_description_field],
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider_name = models.CharField(max_length=20, default="MOCK")
    prompt_version = models.CharField(max_length=20, default="v1")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Solicitud #{self.pk} ({self.get_status_display()})"


class OrganizationalPlan(models.Model):
    class ReviewStatus(models.TextChoices):
        DRAFT = "DRAFT", "Borrador para revision"
        REVIEWED = "REVIEWED", "Revisado"
        APPROVED = "APPROVED", "Aprobado"

    request = models.OneToOneField(
        OrganizationGenerationRequest,
        on_delete=models.CASCADE,
        related_name="plan",
    )
    company_name = models.CharField(
        max_length=160,
        validators=[MinLengthValidator(MIN_COMPANY_NAME_LENGTH)],
    )
    company_summary = models.TextField(
        max_length=MAX_COMPANY_SUMMARY_LENGTH,
        validators=[MinLengthValidator(MIN_COMPANY_SUMMARY_LENGTH)],
    )
    assumptions = models.JSONField(default=list, validators=[validate_assumptions])
    review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.company_name


class OrganizationalUnit(models.Model):
    plan = models.ForeignKey(
        OrganizationalPlan,
        on_delete=models.CASCADE,
        related_name="units",
    )
    code = models.CharField(
        max_length=40,
        validators=[
            MinLengthValidator(2),
            RegexValidator(
                regex=r"^[A-Z][A-Z0-9_]*$",
                message="El codigo debe usar mayusculas, numeros o guiones bajos.",
            ),
        ],
    )
    name = models.CharField(
        max_length=120,
        validators=[MinLengthValidator(MIN_UNIT_NAME_LENGTH)],
    )
    description = models.TextField(
        max_length=MAX_UNIT_DESCRIPTION_LENGTH,
        validators=[MinLengthValidator(MIN_UNIT_DESCRIPTION_LENGTH)],
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("plan", "code"),
                name="unique_unit_code_per_plan",
            ),
            models.UniqueConstraint(
                fields=("plan",),
                condition=models.Q(parent__isnull=True),
                name="unique_root_unit_per_plan",
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="unit_cannot_be_own_parent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.plan.company_name} - {self.name}"


class Vacancy(models.Model):
    class Currency(models.TextChoices):
        COP = "COP", "COP"
        USD = "USD", "USD"
        EUR = "EUR", "EUR"
        MXN = "MXN", "MXN"

    class SalaryPeriod(models.TextChoices):
        HOURLY = "HOURLY", "Por hora"
        MONTHLY = "MONTHLY", "Mensual"
        ANNUAL = "ANNUAL", "Anual"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        PUBLISHED = "PUBLISHED", "Publicada"
        CLOSED = "CLOSED", "Cerrada"

    plan = models.ForeignKey(
        OrganizationalPlan,
        on_delete=models.CASCADE,
        related_name="vacancies",
    )
    department = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        related_name="vacancies",
    )
    name = models.CharField(
        max_length=140,
        validators=[MinLengthValidator(MIN_VACANCY_NAME_LENGTH)],
    )
    available_positions = models.PositiveIntegerField(
        validators=[
            MinValueValidator(MIN_AVAILABLE_POSITIONS),
            MaxValueValidator(MAX_AVAILABLE_POSITIONS),
        ]
    )
    salary_min = models.DecimalField(max_digits=14, decimal_places=2)
    salary_max = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.COP)
    salary_period = models.CharField(
        max_length=10,
        choices=SalaryPeriod.choices,
        default=SalaryPeriod.MONTHLY,
    )
    description = models.TextField(
        max_length=MAX_VACANCY_DESCRIPTION_LENGTH,
        validators=[MinLengthValidator(MIN_VACANCY_DESCRIPTION_LENGTH)],
    )
    required_knowledge = models.JSONField(
        default=list,
        validators=[validate_required_knowledge],
    )
    reports_to = models.CharField(max_length=140, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("department__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("plan", "department", "name"),
                name="unique_vacancy_per_department_and_plan",
            ),
            models.UniqueConstraint(
                Lower("name"),
                "plan",
                "department",
                name="unique_vacancy_name_ci_per_department_and_plan",
            ),
            models.CheckConstraint(
                condition=models.Q(available_positions__gte=MIN_AVAILABLE_POSITIONS),
                name="vacancy_positions_at_least_one",
            ),
            models.CheckConstraint(
                condition=models.Q(available_positions__lte=MAX_AVAILABLE_POSITIONS),
                name="vacancy_positions_at_most_500",
            ),
            models.CheckConstraint(
                condition=models.Q(salary_min__gte=0),
                name="vacancy_salary_min_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(salary_max__gte=models.F("salary_min")),
                name="vacancy_salary_range_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.available_positions})"
