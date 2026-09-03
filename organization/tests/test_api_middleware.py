from django.test import TestCase


class APIRequestContextMiddlewareTests(TestCase):
    def test_api_response_exposes_version_and_generated_request_id(self):
        response = self.client.get("/api/v1/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-API-Version"], "v1")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_safe_request_id_is_propagated(self):
        response = self.client.get(
            "/api/v1/plans/",
            HTTP_X_REQUEST_ID="demo-entrega-1",
        )

        self.assertEqual(response["X-Request-ID"], "demo-entrega-1")
