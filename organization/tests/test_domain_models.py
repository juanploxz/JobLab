from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organization.models import (
    OrganizationalPlan,
    OrganizationalUnit,
    OrganizationGenerationRequest,
    Vacancy,
)


class DomainModelValidationTests(TestCase):
    def setUp(self):
        self.request = OrganizationGenerationRequest.objects.create(
            company_description="Descripcion valida para una empresa de pruebas " * 3
        )
        self.plan = OrganizationalPlan.objects.create(
            request=self.request,
            company_name="Empresa de Prueba",
            company_summary="Resumen suficientemente completo para el plan de prueba.",
            assumptions=["Operacion inicial en Colombia"],
        )
        self.root = OrganizationalUnit.objects.create(
            plan=self.plan,
            code="MANAGEMENT",
            name="Direccion",
            description="Departamento responsable de la estrategia general de la empresa.",
        )

    def vacancy(self, **overrides) -> Vacancy:
        values = {
            "plan": self.plan,
            "department": self.root,
            "name": "Gerente General",
            "available_positions": 1,
            "salary_min": Decimal("5000000"),
            "salary_max": Decimal("7000000"),
            "currency": Vacancy.Currency.COP,
            "salary_period": Vacancy.SalaryPeriod.MONTHLY,
            "description": (
                "Dirige la estrategia, el presupuesto y el equipo inicial de la empresa."
            ),
            "required_knowledge": ["Estrategia", "Finanzas"],
        }
        values.update(overrides)
        return Vacancy(**values)

    def test_company_description_validator_runs_at_entity_boundary(self):
        request = OrganizationGenerationRequest(company_description="Muy corta")

        with self.assertRaisesRegex(ValidationError, "80 caracteres"):
            request.full_clean()

    def test_assumptions_must_be_a_list_of_strings(self):
        self.plan.assumptions = "No es una lista"

        with self.assertRaisesRegex(ValidationError, "debe ser una lista"):
            self.plan.full_clean()

    def test_required_knowledge_rejects_non_text_and_duplicates(self):
        invalid_type = self.vacancy(required_knowledge=["Python", 42])
        duplicates = self.vacancy(required_knowledge=["Python", " python "])

        with self.assertRaisesRegex(ValidationError, "debe ser texto"):
            invalid_type.full_clean()
        with self.assertRaisesRegex(ValidationError, "duplicados"):
            duplicates.full_clean()

    def test_only_one_root_unit_is_allowed_per_plan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationalUnit.objects.create(
                plan=self.plan,
                code="SECOND_ROOT",
                name="Otra direccion",
                description="Otra unidad raiz que haria ambigua la estructura organizacional.",
            )

    def test_unit_cannot_be_its_own_parent(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationalUnit.objects.filter(pk=self.root.pk).update(parent_id=self.root.pk)

    def test_available_positions_has_an_entity_and_database_upper_bound(self):
        vacancy = self.vacancy(available_positions=501)

        with self.assertRaisesRegex(ValidationError, "500"):
            vacancy.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Vacancy.objects.create(
                **{
                    field: getattr(vacancy, field)
                    for field in (
                        "plan",
                        "department",
                        "name",
                        "available_positions",
                        "salary_min",
                        "salary_max",
                        "currency",
                        "salary_period",
                        "description",
                        "required_knowledge",
                        "reports_to",
                        "status",
                    )
                }
            )

    def test_vacancy_name_is_unique_case_insensitively_in_database(self):
        self.vacancy(name="Analista de Datos").save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.vacancy(name="analista de datos").save()
