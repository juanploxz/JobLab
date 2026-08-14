from django.core.validators import MinValueValidator
from django.db import models


class OrganizationGenerationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        PROCESSING = "PROCESSING", "Procesando"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallida"

    company_description = models.TextField(max_length=5000)
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
    company_name = models.CharField(max_length=160)
    company_summary = models.TextField()
    assumptions = models.JSONField(default=list)
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
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    description = models.TextField()
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
            )
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
    name = models.CharField(max_length=140)
    available_positions = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    salary_min = models.DecimalField(max_digits=14, decimal_places=2)
    salary_max = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.COP)
    salary_period = models.CharField(
        max_length=10,
        choices=SalaryPeriod.choices,
        default=SalaryPeriod.MONTHLY,
    )
    description = models.TextField()
    required_knowledge = models.JSONField(default=list)
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
            models.CheckConstraint(
                condition=models.Q(available_positions__gte=1),
                name="vacancy_positions_at_least_one",
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
