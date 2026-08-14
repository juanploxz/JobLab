import json

from django.test import SimpleTestCase

from organization.domain.exceptions import ProposalParsingError
from organization.infra.ai.response_parser import OrganizationResponseParser


class OrganizationResponseParserTests(SimpleTestCase):
    def setUp(self):
        self.parser = OrganizationResponseParser()
        self.payload = {
            "company_name": "Empresa Valida",
            "company_summary": "Una empresa valida con un resumen suficientemente detallado para la prueba.",
            "assumptions": ["Operacion inicial en Colombia"],
            "departments": [
                {
                    "code": "MANAGEMENT",
                    "name": "Direccion",
                    "description": "Responsable de la estrategia y de las decisiones principales.",
                    "parent_code": None,
                },
                {
                    "code": "TECH",
                    "name": "Tecnologia",
                    "description": "Responsable de construir y mantener el producto tecnologico.",
                    "parent_code": "MANAGEMENT",
                },
            ],
            "vacancies": [
                {
                    "department_code": "TECH",
                    "name": "Desarrollador",
                    "available_positions": 1,
                    "salary_min": "3000000",
                    "salary_max": "5000000",
                    "currency": "COP",
                    "salary_period": "MONTHLY",
                    "description": "Construye componentes del producto y automatiza las pruebas necesarias para entregarlo.",
                    "required_knowledge": ["Python", "Django"],
                    "reports_to": "Director",
                }
            ],
        }

    def test_parses_valid_json_into_domain_schema(self):
        proposal = self.parser.parse(json.dumps(self.payload))

        self.assertEqual(proposal.departments[1].code, "TECH")
        self.assertEqual(proposal.vacancies[0].currency, "COP")

    def test_rejects_markdown_wrapped_response(self):
        with self.assertRaisesRegex(ProposalParsingError, "Markdown"):
            self.parser.parse("```json\n{}\n```")

    def test_rejects_unknown_department_reference(self):
        self.payload["vacancies"][0]["department_code"] = "UNKNOWN"

        with self.assertRaisesRegex(ProposalParsingError, "departamento inexistente"):
            self.parser.parse(json.dumps(self.payload))

    def test_rejects_multiple_roots(self):
        self.payload["departments"][1]["parent_code"] = None

        with self.assertRaisesRegex(ProposalParsingError, "exactamente un departamento raiz"):
            self.parser.parse(json.dumps(self.payload))

    def test_rejects_extra_fields(self):
        self.payload["unexpected"] = True

        with self.assertRaisesRegex(ProposalParsingError, "Extra inputs"):
            self.parser.parse(json.dumps(self.payload))
