from decimal import Decimal

from organization.domain.schemas import (
    DepartmentProposal,
    OrganizationProposal,
    VacancyProposal,
)


class MockOrganizationProvider:
    """Deterministic local provider for development, demos and automated tests."""

    name = "MOCK"

    _TECH_TERMS = {"software", "tecnologia", "tecnologica", "plataforma", "aplicacion", "ia"}

    def generate(self, company_description: str) -> OrganizationProposal:
        lowered = company_description.casefold()
        is_technology_company = any(term in lowered for term in self._TECH_TERMS)
        departments = self._departments(is_technology_company)
        vacancies = self._vacancies(is_technology_company)
        return OrganizationProposal(
            company_name=self._company_name(lowered),
            company_summary=(
                "Propuesta inicial para una empresa que busca convertir su idea y capacidades "
                f"en una operacion sostenible. Contexto recibido: {company_description[:1200]}"
            ),
            assumptions=[
                "Se supone una operacion inicial en Colombia y salarios expresados en COP.",
                "Se prioriza un equipo pequeno que pueda crecer despues de validar la demanda.",
                "Las cifras salariales son estimaciones y requieren revision humana.",
            ],
            departments=departments,
            vacancies=vacancies,
        )

    @staticmethod
    def _company_name(description: str) -> str:
        if "restaurante" in description or "alimentos" in description:
            return "Empresa Gastronomica en Formacion"
        if "software" in description or "tecnologia" in description or "plataforma" in description:
            return "Empresa Tecnologica en Formacion"
        if "consultoria" in description:
            return "Firma Consultora en Formacion"
        return "Empresa en Formacion"

    @staticmethod
    def _departments(include_technology: bool) -> list[DepartmentProposal]:
        departments = [
            DepartmentProposal(
                code="MANAGEMENT",
                name="Direccion General",
                description="Define la estrategia, asigna recursos y supervisa el cumplimiento de los objetivos empresariales.",
                parent_code=None,
            ),
            DepartmentProposal(
                code="OPERATIONS",
                name="Operaciones",
                description="Convierte la propuesta de valor en procesos repetibles, medibles y orientados a la calidad.",
                parent_code="MANAGEMENT",
            ),
            DepartmentProposal(
                code="COMMERCIAL",
                name="Comercial y Mercadeo",
                description="Valida la demanda, atrae clientes y administra el ciclo comercial de la empresa.",
                parent_code="MANAGEMENT",
            ),
        ]
        if include_technology:
            departments.append(
                DepartmentProposal(
                    code="TECHNOLOGY",
                    name="Tecnologia y Producto",
                    description="Disena, construye y mantiene el producto digital y la infraestructura tecnica.",
                    parent_code="MANAGEMENT",
                )
            )
        return departments

    @classmethod
    def _vacancies(cls, include_technology: bool) -> list[VacancyProposal]:
        vacancies = [
            VacancyProposal(
                department_code="MANAGEMENT",
                name="Gerente General",
                available_positions=1,
                salary_min=Decimal("6000000"),
                salary_max=Decimal("9000000"),
                currency="COP",
                salary_period="MONTHLY",
                description="Lidera la estrategia, el presupuesto y las prioridades de la empresa durante su etapa inicial de crecimiento.",
                required_knowledge=["Planeacion estrategica", "Finanzas para negocios", "Gestion de equipos"],
                reports_to=None,
            ),
            VacancyProposal(
                department_code="OPERATIONS",
                name="Coordinador de Operaciones",
                available_positions=1,
                salary_min=Decimal("3500000"),
                salary_max=Decimal("4800000"),
                currency="COP",
                salary_period="MONTHLY",
                description="Disena y controla procesos operativos, indicadores de calidad y capacidad para cumplir la propuesta de valor.",
                required_knowledge=["Diseno de procesos", "Indicadores de gestion", "Mejora continua"],
                reports_to="Gerente General",
            ),
            VacancyProposal(
                department_code="COMMERCIAL",
                name="Ejecutivo Comercial",
                available_positions=2,
                salary_min=Decimal("2500000"),
                salary_max=Decimal("3800000"),
                currency="COP",
                salary_period="MONTHLY",
                description="Desarrolla oportunidades comerciales, documenta necesidades del cliente y mantiene el embudo de ventas.",
                required_knowledge=["Ventas consultivas", "CRM", "Negociacion"],
                reports_to="Gerente General",
            ),
        ]
        if include_technology:
            vacancies.extend(
                [
                    VacancyProposal(
                        department_code="TECHNOLOGY",
                        name="Lider Tecnico",
                        available_positions=1,
                        salary_min=Decimal("6500000"),
                        salary_max=Decimal("9000000"),
                        currency="COP",
                        salary_period="MONTHLY",
                        description="Define la arquitectura del producto, coordina las decisiones tecnicas y protege la calidad del software.",
                        required_knowledge=["Arquitectura de software", "Django", "Bases de datos", "Seguridad"],
                        reports_to="Gerente General",
                    ),
                    VacancyProposal(
                        department_code="TECHNOLOGY",
                        name="Desarrollador Full Stack",
                        available_positions=2,
                        salary_min=Decimal("4000000"),
                        salary_max=Decimal("6000000"),
                        currency="COP",
                        salary_period="MONTHLY",
                        description="Implementa funcionalidades del producto, automatiza pruebas y colabora en entregas pequenas y frecuentes.",
                        required_knowledge=["Python", "Django", "JavaScript", "Git"],
                        reports_to="Lider Tecnico",
                    ),
                ]
            )
        return vacancies
