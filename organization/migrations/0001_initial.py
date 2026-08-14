# Generated manually for the initial JobLab schema.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OrganizationGenerationRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_description", models.TextField(max_length=5000)),
                ("status", models.CharField(choices=[("PENDING", "Pendiente"), ("PROCESSING", "Procesando"), ("COMPLETED", "Completada"), ("FAILED", "Fallida")], default="PENDING", max_length=16)),
                ("provider_name", models.CharField(default="MOCK", max_length=20)),
                ("prompt_version", models.CharField(default="v1", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="OrganizationalPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(max_length=160)),
                ("company_summary", models.TextField()),
                ("assumptions", models.JSONField(default=list)),
                ("review_status", models.CharField(choices=[("DRAFT", "Borrador para revision"), ("REVIEWED", "Revisado"), ("APPROVED", "Aprobado")], default="DRAFT", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="plan", to="organization.organizationgenerationrequest")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="OrganizationalUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField()),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="organization.organizationalunit")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="units", to="organization.organizationalplan")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Vacancy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140)),
                ("available_positions", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("salary_min", models.DecimalField(decimal_places=2, max_digits=14)),
                ("salary_max", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(choices=[("COP", "COP"), ("USD", "USD"), ("EUR", "EUR"), ("MXN", "MXN")], default="COP", max_length=3)),
                ("salary_period", models.CharField(choices=[("HOURLY", "Por hora"), ("MONTHLY", "Mensual"), ("ANNUAL", "Anual")], default="MONTHLY", max_length=10)),
                ("description", models.TextField()),
                ("required_knowledge", models.JSONField(default=list)),
                ("reports_to", models.CharField(blank=True, max_length=140)),
                ("status", models.CharField(choices=[("DRAFT", "Borrador"), ("PUBLISHED", "Publicada"), ("CLOSED", "Cerrada")], default="DRAFT", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vacancies", to="organization.organizationalunit")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vacancies", to="organization.organizationalplan")),
            ],
            options={"ordering": ("department__name", "name")},
        ),
        migrations.AddConstraint(
            model_name="organizationalunit",
            constraint=models.UniqueConstraint(fields=("plan", "code"), name="unique_unit_code_per_plan"),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.UniqueConstraint(fields=("plan", "department", "name"), name="unique_vacancy_per_department_and_plan"),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.CheckConstraint(condition=models.Q(("available_positions__gte", 1)), name="vacancy_positions_at_least_one"),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.CheckConstraint(condition=models.Q(("salary_min__gte", 0)), name="vacancy_salary_min_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.CheckConstraint(condition=models.Q(("salary_max__gte", models.F("salary_min"))), name="vacancy_salary_range_valid"),
        ),
    ]
