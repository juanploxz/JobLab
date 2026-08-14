from decimal import Decimal

from django.test import TestCase

from organization.domain.builders import VacancyBuilder
from organization.domain.exceptions import DomainValidationError
from organization.models import (
    OrganizationalPlan,
    OrganizationalUnit,
    OrganizationGenerationRequest,
)


class VacancyBuilderTests(TestCase):
    def setUp(self):
        request = OrganizationGenerationRequest.objects.create(
            company_description="Descripcion valida para una empresa de pruebas " * 3
        )
        self.plan = OrganizationalPlan.objects.create(
            request=request,
            company_name="Empresa de Prueba",
            company_summary="Resumen suficientemente completo para el plan de prueba.",
        )
        self.department = OrganizationalUnit.objects.create(
            plan=self.plan,
            code="TECH",
            name="Tecnologia",
            description="Departamento responsable del producto y la tecnologia.",
        )

    def valid_builder(self) -> VacancyBuilder:
        return (
            VacancyBuilder()
            .for_plan(self.plan)
            .in_department(self.department)
            .with_name("Desarrollador Backend")
            .with_positions(2)
            .with_salary(Decimal("4000000"), Decimal("6000000"), "COP", "MONTHLY")
            .with_description(
                "Implementa servicios de negocio, pruebas automatizadas y mejoras continuas del producto."
            )
            .requiring(["Python", "Django", "Python"])
            .reporting_to("Lider Tecnico")
        )

    def test_build_returns_valid_unsaved_vacancy(self):
        vacancy = self.valid_builder().build()

        self.assertIsNone(vacancy.pk)
        self.assertEqual(vacancy.available_positions, 2)
        self.assertEqual(vacancy.required_knowledge, ["Python", "Django"])

    def test_rejects_missing_required_fields(self):
        with self.assertRaisesRegex(DomainValidationError, "Faltan campos"):
            VacancyBuilder().with_name("Vacante incompleta").build()

    def test_rejects_invalid_salary_range_before_save(self):
        builder = self.valid_builder().with_salary(7000000, 5000000, "COP")

        with self.assertRaisesRegex(DomainValidationError, "salario minimo"):
            builder.build()

    def test_rejects_department_from_another_plan(self):
        other_request = OrganizationGenerationRequest.objects.create(
            company_description="Otra descripcion empresarial valida " * 4
        )
        other_plan = OrganizationalPlan.objects.create(
            request=other_request,
            company_name="Otra Empresa",
            company_summary="Otro resumen suficientemente completo para la prueba.",
        )

        with self.assertRaisesRegex(DomainValidationError, "no pertenece"):
            self.valid_builder().for_plan(other_plan).build()
