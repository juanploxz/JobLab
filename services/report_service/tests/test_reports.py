import unittest
from unittest.mock import patch

import fakeredis

from report_service import create_app
from report_service.clients import PlanNotFound, UpstreamUnavailable
from report_service.notifiers import EmailNotifier, LogNotifier, build_notifier
from report_service.stores import RedisStore, get_store
from report_service.tasks import plan_created

PLAN = {
    "id": 3,
    "company_name": "Empresa Tecnologica en Formacion",
    "metrics": {"department_count": 4, "vacancy_count": 1, "total_positions": 2},
    "vacancies": [
        {
            "id": 10,
            "department_name": "Tecnologia",
            "name": "Desarrollador Full Stack",
            "available_positions": 2,
            "salary_min": "4000000.00",
            "salary_max": "6000000.00",
            "currency": "COP",
            "salary_period": "MONTHLY",
            "required_knowledge": ["Python", "Django"],
            "reports_to": "Lider Tecnico",
        }
    ],
}

STORE_URL = "memory://reports-tests"


def make_app():
    return create_app(
        {
            "TESTING": True,
            "CELERY_TASK_ALWAYS_EAGER": True,
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
            "NOTIFICATION_STORE_URL": STORE_URL,
            "INTEGRATION_SERVICE_URL": "",
        }
    )


class ReportApiTests(unittest.TestCase):
    def setUp(self):
        self.client = make_app().test_client()

    def test_report_is_accepted_processed_and_downloadable(self):
        with patch("report_service.tasks.PlanServiceClient.get_plan", return_value=PLAN):
            response = self.client.post(
                "/api/v2/reports/", json={"plan_id": 3, "format": "csv"}, headers={"Accept-Language": "en"}
            )

        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertTrue(response.headers["Location"].endswith(f"/api/v2/reports/{body['task_id']}/"))

        status = self.client.get(f"/api/v2/reports/{body['task_id']}/").get_json()
        self.assertEqual(status["status"], "SUCCESS")
        self.assertIsNotNone(status["download_url"])

        download = self.client.get(f"/api/v2/reports/{body['task_id']}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        text = download.get_data(as_text=True)
        self.assertIn("Desarrollador Full Stack", text)
        self.assertIn("Organizational plan report", text)

        kinds = [item["type"] for item in get_store(STORE_URL).notifications()]
        self.assertIn("report.ready", kinds)

    def test_json_report(self):
        with patch("report_service.tasks.PlanServiceClient.get_plan", return_value=PLAN):
            task_id = self.client.post("/api/v2/reports/", json={"plan_id": 3, "format": "json"}).get_json()["task_id"]

        download = self.client.get(f"/api/v2/reports/{task_id}/download/")

        self.assertEqual(download.headers["Content-Type"], "application/json")
        self.assertEqual(download.get_json()["plan"]["id"], 3)

    def test_missing_plan_fails_without_retry(self):
        with patch("report_service.tasks.PlanServiceClient.get_plan", side_effect=PlanNotFound(9)) as mocked:
            task_id = self.client.post("/api/v2/reports/", json={"plan_id": 9}).get_json()["task_id"]

        status = self.client.get(f"/api/v2/reports/{task_id}/").get_json()
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(status["status"], "FAILURE")
        self.assertEqual(status["error"]["code"], "plan_not_found")
        not_ready = self.client.get(f"/api/v2/reports/{task_id}/download/")
        self.assertEqual(not_ready.status_code, 409)

    def test_transient_failure_is_retried(self):
        side_effect = [UpstreamUnavailable("x"), PLAN]
        with patch("report_service.tasks.PlanServiceClient.get_plan", side_effect=side_effect) as mocked:
            response = self.client.post("/api/v2/reports/", json={"plan_id": 3})

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(response.get_json()["status"], "SUCCESS")

    def test_validation_and_unknown_reports(self):
        cases = [{"plan_id": "3"}, {"plan_id": 0}, {"plan_id": True}, {"plan_id": 3, "format": "pdf"}, []]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/v2/reports/", json=payload).status_code, 400)
        self.assertEqual(self.client.get("/api/v2/reports/not-a-task/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v2/reports/{'a' * 32}/").status_code, 404)

    def test_notifications_endpoint_and_event_consumer(self):
        plan_created({"plan_id": 77, "company_name": "ACME", "vacancy_count": 2, "total_positions": 3})

        body = self.client.get("/api/v2/notifications/?limit=5").get_json()

        self.assertEqual(body["results"][0]["type"], "plan.created")
        self.assertEqual(body["results"][0]["data"]["plan_id"], 77)

    def test_health_reports_store(self):
        self.assertEqual(self.client.get("/health").get_json()["checks"]["redis"], "ok")


class StoreAndNotifierTests(unittest.TestCase):
    def test_redis_store_keeps_bounded_log_and_registry(self):
        store = RedisStore(fakeredis.FakeRedis(decode_responses=True), max_items=2)
        for number in range(3):
            store.add_notification("plan.created", {"plan_id": number})
        store.register_report("abc", {"plan_id": 1}, ttl_seconds=60)

        self.assertEqual([n["data"]["plan_id"] for n in store.notifications()], [2, 1])
        self.assertEqual(store.report("abc"), {"plan_id": 1})
        self.assertTrue(store.ping())

    def test_notifier_factory_and_email(self):
        self.assertIsInstance(build_notifier({"SMTP_HOST": ""}), LogNotifier)
        sent = []

        class FakeSMTP:
            def __init__(self, host, port, timeout):
                self.host = host

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def starttls(self):
                sent.append("tls")

            def login(self, user, password):
                sent.append("login")

            def send_message(self, message):
                sent.append(message["Subject"])

        config = {
            "SMTP_HOST": "smtp.test",
            "SMTP_PORT": 587,
            "SMTP_USER": "u",
            "SMTP_PASSWORD": "p",
            "SMTP_USE_TLS": True,
            "NOTIFY_EMAIL_FROM": "a@test",
            "NOTIFY_EMAIL_TO": "b@test",
        }
        self.assertIsInstance(build_notifier(config), EmailNotifier)
        EmailNotifier(config, smtp_factory=FakeSMTP).send("Asunto", "Cuerpo")
        self.assertEqual(sent, ["tls", "login", "Asunto"])
