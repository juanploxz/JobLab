import json
import unittest
from unittest.mock import patch

from google.genai import types

from plan_service.domain.exceptions import ConfigurationError, GenerationUnavailableError
from plan_service.infra.ai.factory import AIProviderFactory
from plan_service.infra.ai.google_provider import (
    SYSTEM_INSTRUCTION,
    GoogleOrganizationProvider,
    proposal_json_schema,
)
from plan_service.infra.ai.mock_provider import MockOrganizationProvider
from tests.base import DESCRIPTION, PlanServiceTestCase

FORBIDDEN_KEYS = {"$ref", "$defs", "$schema", "additionalProperties", "title"}


def _walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """Stands in for genai.Client: records constructor kwargs and generate_content calls."""

    instances = []

    def __init__(self, *, text=None, error=None, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self._text = text
        self._error = error
        self.models = self
        FakeClient.instances.append(self)

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return FakeResponse(self._text)


def factory_returning(**behaviour):
    FakeClient.instances = []
    return lambda **kwargs: FakeClient(**behaviour, **kwargs)


VALID_JSON = MockOrganizationProvider().generate(DESCRIPTION).model_dump_json()


class PromptSchemaTests(unittest.TestCase):
    def test_schema_is_self_contained_and_matches_the_parser_contract(self):
        schema = proposal_json_schema()

        self.assertEqual(set(_walk_keys(schema)) & FORBIDDEN_KEYS, set())
        self.assertEqual(
            schema["required"], ["company_name", "company_summary", "departments", "vacancies"]
        )
        department = schema["properties"]["departments"]["items"]
        vacancy = schema["properties"]["vacancies"]["items"]
        self.assertEqual(set(department["properties"]), {"code", "name", "description", "parent_code"})
        self.assertEqual(
            set(vacancy["properties"]),
            {
                "department_code", "name", "available_positions", "salary_min", "salary_max",
                "currency", "salary_period", "description", "required_knowledge", "reports_to",
            },
        )

    def test_system_instruction_embeds_the_exact_schema(self):
        marker = "Esquema JSON exacto que debe cumplir la respuesta:\n"
        embedded = json.loads(SYSTEM_INSTRUCTION.split(marker, 1)[1])

        self.assertEqual(embedded, proposal_json_schema())
        self.assertIn('"currency"', SYSTEM_INSTRUCTION)
        self.assertNotIn("salary_currency", SYSTEM_INSTRUCTION)


class GoogleProviderTests(unittest.TestCase):
    def provider(self, **behaviour):
        return GoogleOrganizationProvider(
            api_key="test-key", model="gemini-test", client_factory=factory_returning(**behaviour)
        )

    def test_client_gets_60s_timeout_and_request_uses_json_mode_without_schema(self):
        proposal = self.provider(text=VALID_JSON).generate(DESCRIPTION)

        client = FakeClient.instances[0]
        self.assertEqual(client.kwargs["api_key"], "test-key")
        self.assertIsInstance(client.kwargs["http_options"], types.HttpOptions)
        self.assertEqual(client.kwargs["http_options"].timeout, 60_000)
        call = client.calls[0]
        self.assertEqual(call["model"], "gemini-test")
        self.assertIn(DESCRIPTION, call["contents"])
        config = call["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIsNone(config.response_schema)
        self.assertIsNone(config.response_json_schema)
        self.assertEqual(config.system_instruction, SYSTEM_INSTRUCTION)
        self.assertEqual(proposal.company_name, json.loads(VALID_JSON)["company_name"])

    def test_json_mode_answer_with_numeric_salaries_and_nulls_is_parsed(self):
        answer = json.loads(VALID_JSON)
        for vacancy in answer["vacancies"]:
            vacancy["salary_min"] = float(vacancy["salary_min"])
            vacancy["salary_max"] = int(float(vacancy["salary_max"]))
            vacancy["reports_to"] = None

        proposal = self.provider(text=json.dumps(answer)).generate(DESCRIPTION)

        self.assertEqual(len(proposal.vacancies), len(answer["vacancies"]))
        self.assertIsNone(proposal.vacancies[0].reports_to)

    def test_answer_with_wrong_field_names_is_rejected(self):
        answer = json.loads(VALID_JSON)
        answer["vacancies"][0]["salary_currency"] = answer["vacancies"][0].pop("currency")

        with self.assertLogs("plan_service.infra.ai.google_provider", "ERROR") as logs:
            with self.assertRaises(GenerationUnavailableError):
                self.provider(text=json.dumps(answer)).generate(DESCRIPTION)
        self.assertIn("salary_currency", logs.output[0])

    def test_sdk_error_is_logged_and_wrapped(self):
        provider = self.provider(error=RuntimeError("400 INVALID_ARGUMENT response_schema"))

        with self.assertLogs("plan_service.infra.ai.google_provider", "ERROR") as logs:
            with self.assertRaises(GenerationUnavailableError) as raised:
                provider.generate(DESCRIPTION)

        self.assertIn("INVALID_ARGUMENT", logs.output[0])
        self.assertIn("Traceback", logs.output[0])
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)

    def test_invalid_model_output_is_logged_and_wrapped(self):
        for text in ("", "```json {}```", '{"company_name": "x"}'):
            with self.subTest(text=text), self.assertLogs(
                "plan_service.infra.ai.google_provider", "ERROR"
            ), self.assertRaises(GenerationUnavailableError):
                self.provider(text=text).generate(DESCRIPTION)

    def test_factory_passes_configured_timeout(self):
        provider = AIProviderFactory.create(
            {"AI_PROVIDER": "GOOGLE", "GEMINI_API_KEY": "k", "GEMINI_TIMEOUT_MS": "90000"}
        )
        self.assertEqual(provider.timeout_ms, 90_000)
        with self.assertRaises(ConfigurationError):
            AIProviderFactory.create({"AI_PROVIDER": "GOOGLE", "GEMINI_API_KEY": ""})


class GoogleProviderThroughApiTests(PlanServiceTestCase):
    def _with_provider(self, **behaviour):
        provider = GoogleOrganizationProvider(
            api_key="k", model="m", client_factory=factory_returning(**behaviour)
        )
        return patch("plan_service.bootstrap.ai_provider", return_value=provider)

    def test_valid_gemini_answer_creates_plan(self):
        with self._with_provider(text=VALID_JSON):
            response = self.client.post("/api/v2/plans/", json={"company_description": DESCRIPTION})

        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["provider_name"], "GOOGLE")

    def test_gemini_failure_returns_503(self):
        with self._with_provider(error=TimeoutError("read timeout")), self.assertLogs(
            "plan_service.infra.ai.google_provider", "ERROR"
        ):
            response = self.client.post("/api/v2/plans/", json={"company_description": DESCRIPTION})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "generation_service_unavailable")
