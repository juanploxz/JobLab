from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_reports_database(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"]["database"], "ok")

    def test_internal_hosts_are_always_allowed(self):
        response = self.client.get("/health/", HTTP_HOST="django")

        self.assertEqual(response.status_code, 200)
