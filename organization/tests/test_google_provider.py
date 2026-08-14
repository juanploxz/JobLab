import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from organization.infra.ai.google_provider import GoogleOrganizationProvider


VALID_RESPONSE = json.dumps(
    {
        "company_name": "Empresa Generada",
        "company_summary": "Una empresa generada con un resumen suficientemente detallado para validar el adaptador.",
        "assumptions": ["Operacion inicial en Colombia"],
        "departments": [
            {
                "code": "MANAGEMENT",
                "name": "Direccion",
                "description": "Responsable de definir y supervisar la estrategia general.",
                "parent_code": None,
            }
        ],
        "vacancies": [
            {
                "department_code": "MANAGEMENT",
                "name": "Gerente General",
                "available_positions": 1,
                "salary_min": "5000000",
                "salary_max": "7000000",
                "currency": "COP",
                "salary_period": "MONTHLY",
                "description": "Dirige la estrategia, el presupuesto y el equipo inicial de la empresa durante su crecimiento.",
                "required_knowledge": ["Estrategia", "Finanzas"],
                "reports_to": None,
            }
        ],
    }
)


@override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-test-model")
class GoogleOrganizationProviderTests(SimpleTestCase):
    @patch("google.genai.Client")
    def test_requests_structured_json_without_external_call(self, client_class):
        client_class.return_value.models.generate_content.return_value.text = VALID_RESPONSE
        provider = GoogleOrganizationProvider()

        proposal = provider.generate(
            "Somos una empresa de tecnologia con suficiente contexto para generar "
            "una estructura de prueba segura y coherente para nuestro equipo inicial."
        )

        self.assertEqual(proposal.company_name, "Empresa Generada")
        client_class.assert_called_once_with(api_key="test-key")
        call = client_class.return_value.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-test-model")
        self.assertEqual(call.kwargs["config"].response_mime_type, "application/json")
        self.assertIn("INICIO DESCRIPCION NO CONFIABLE", call.kwargs["contents"])
