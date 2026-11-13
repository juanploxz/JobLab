import json
import unittest
from unittest.mock import patch

from google.genai import types

from plan_service.domain.exceptions import ConfigurationError, GenerationUnavailableError
from plan_service.infra.ai.factory import AIProviderFactory
from plan_service.infra.ai.google_provider import GoogleOrganizationProvider, build_response_schema
from plan_service.infra.ai.mock_provider import MockOrganizationProvider
from tests.base import DESCRIPTION, PlanServiceTestCase

FORBIDDEN_KEYS = {"$ref", "$defs", "$schema", "additionalProperties", "additional_properties", "title", "anyOf", "default"}


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


class ResponseSchemaTests(unittest.TestCase):
    def test_schema_has_no_constructs_rejected_by_gemini(self):
        schema = build_response_schema()

        self.assertEqual(set(_walk_keys(schema)) & FORBIDDEN_KEYS, set())
        self.assertEqual(schema["type"], "OBJECT")
        self.assertEqual(
            schema["required"], ["company_name", "company_summary", "departments", "vacancies"]
        )

    def test_nested_definitions_are_inlined(self):
        schema = build_response_schema()
        department = schema["properties"]["departments"]["items"]
        vacancy = schema["properties"]["vacancies"]["items"]

        self.assertEqual(department["type"], "OBJECT")
        self.assertTrue(department["properties"]["parent_code"]["nullable"])
        self.assertEqual(vacancy["properties"]["salary_min"]["type"], "NUMBER")
        self.assertEqual(vacancy["properties"]["currency"]["enum"], ["COP", "USD", "EUR", "MXN"])
        self.assertEqual(vacancy["property_ordering"][0], "department_code")

    def test_schema_is_accepted_by_the_sdk_model(self):
        sdk_schema = types.Schema.model_validate(build_response_schema())

        self.assertEqual(sdk_schema.type, types.Type.OBJECT)
        self.assertIsNone(sdk_schema.ref)
        self.assertIsNone(sdk_schema.defs)
        self.assertIsNone(sdk_schema.additional_properties)
        items = sdk_schema.properties["vacancies"].items
        self.assertEqual(items.properties["available_positions"].type, types.Type.INTEGER)


class GoogleProviderTests(unittest.TestCase):
    def provider(self, **behaviour):
        return GoogleOrganizationProvider(
            api_key="test-key", model="gemini-test", client_factory=factory_returning(**behaviour)
        )

    def test_client_gets_60s_timeout_and_request_uses_structured_json(self):
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
        self.assertIsInstance(config.response_schema, types.Schema)
        self.assertIsNone(config.response_schema.defs)
        self.assertEqual(proposal.company_name, json.loads(VALID_JSON)["company_name"])

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
