from plan_service.extensions import db
from plan_service.models import GenerationRequest, Vacancy
from tests.base import DESCRIPTION, PlanServiceTestCase


class PlanApiContractTests(PlanServiceTestCase):
    def test_post_plan_returns_201_location_and_complete_output(self):
        response = self.client.post("/api/v2/plans/", json={"company_description": DESCRIPTION})

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertTrue(response.headers["Location"].endswith(f"/api/v2/plans/{body['id']}/"))
        self.assertEqual(body["generation_status"], "COMPLETED")
        self.assertEqual(body["provider_name"], "MOCK")
        self.assertGreaterEqual(body["metrics"]["department_count"], 1)
        self.assertEqual(body["metrics"]["vacancy_count"], len(body["vacancies"]))
        self.assertEqual(len([u for u in body["units"] if u["parent_id"] is None]), 1)

    def test_plan_creation_publishes_integration_event(self):
        plan = self.create_plan()

        self.assertEqual(self.events.events[0][0], "plan.created")
        payload = self.events.events[0][1]
        self.assertEqual(payload["plan_id"], plan["id"])
        self.assertEqual(payload["total_positions"], plan["metrics"]["total_positions"])

    def test_list_is_paginated_newest_first(self):
        first = self.create_plan()
        self.create_plan()

        response = self.client.get("/api/v2/plans/?page_size=1")

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 1)
        self.assertNotEqual(body["results"][0]["id"], first["id"])
        self.assertIn("page=2", body["next"])
        self.assertIsNone(body["previous"])

    def test_invalid_page_returns_uniform_404(self):
        self.create_plan()

        response = self.client.get("/api/v2/plans/?page=99")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "page_not_found")

    def test_get_detail_and_missing_plan(self):
        plan = self.create_plan()

        ok = self.client.get(f"/api/v2/plans/{plan['id']}/")
        missing = self.client.get("/api/v2/plans/999/")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["id"], plan["id"])
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"]["code"], "plan_not_found")

    def test_missing_field_returns_400_with_fields(self):
        response = self.client.post("/api/v2/plans/", json={})

        self.assertEqual(response.status_code, 400)
        error = response.get_json()["error"]
        self.assertEqual(error["code"], "invalid_request")
        self.assertIn("company_description", error["fields"])
        self.assertEqual(db.session.query(GenerationRequest).count(), 0)

    def test_malformed_json_returns_parse_error(self):
        response = self.client.post(
            "/api/v2/plans/", data='{"company_description":', content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "parse_error")

    def test_short_description_is_domain_error(self):
        response = self.client.post("/api/v2/plans/", json={"company_description": "corta"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "domain_validation_error")

    def test_method_not_allowed_uses_contract(self):
        response = self.client.delete("/api/v2/plans/")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"]["code"], "method_not_allowed")

    def test_provider_failure_returns_503_and_marks_request_failed(self):
        class BrokenProvider:
            name = "BROKEN"

            def generate(self, description):
                raise RuntimeError("internal detail")

        from unittest.mock import patch

        with patch("plan_service.bootstrap.ai_provider", return_value=BrokenProvider()):
            response = self.client.post("/api/v2/plans/", json={"company_description": DESCRIPTION})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "generation_service_unavailable")
        self.assertNotIn("internal detail", response.get_json()["error"]["detail"])
        request = db.session.query(GenerationRequest).one()
        self.assertEqual(request.status, GenerationRequest.FAILED)
        self.assertEqual(self.events.events, [])

    def test_create_and_get_vacancy(self):
        plan = self.create_plan()
        department_id = plan["units"][0]["id"]

        created = self.client.post(
            f"/api/v2/plans/{plan['id']}/vacancies/", json=self.vacancy_payload(department_id)
        )

        self.assertEqual(created.status_code, 201)
        body = created.get_json()
        self.assertTrue(
            created.headers["Location"].endswith(f"/plans/{plan['id']}/vacancies/{body['id']}/")
        )
        self.assertEqual(body["salary_min"], "6500000.00")
        fetched = self.client.get(f"/api/v2/plans/{plan['id']}/vacancies/{body['id']}/")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(self.events.events[-1][0], "vacancy.created")

    def test_duplicate_vacancy_is_case_insensitive_409(self):
        plan = self.create_plan()
        payload = self.vacancy_payload(plan["units"][0]["id"])
        url = f"/api/v2/plans/{plan['id']}/vacancies/"
        self.client.post(url, json=payload)
        payload["name"] = payload["name"].swapcase()

        response = self.client.post(url, json=payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "vacancy_already_exists")

    def test_department_from_another_plan_returns_404(self):
        first = self.create_plan()
        second = self.create_plan()

        response = self.client.post(
            f"/api/v2/plans/{first['id']}/vacancies/",
            json=self.vacancy_payload(second["units"][0]["id"]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "department_not_found")

    def test_business_rule_enforced_by_builder(self):
        plan = self.create_plan()
        payload = self.vacancy_payload(plan["units"][0]["id"])
        payload["salary_min"], payload["salary_max"] = "9000000", "5000000"

        response = self.client.post(f"/api/v2/plans/{plan['id']}/vacancies/", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "domain_validation_error")
        self.assertEqual(
            db.session.query(Vacancy).filter_by(name="Arquitecto de Integraciones").count(), 0
        )

    def test_missing_vacancy_returns_404(self):
        plan = self.create_plan()

        response = self.client.get(f"/api/v2/plans/{plan['id']}/vacancies/9999/")

        self.assertEqual(response.get_json()["error"]["code"], "vacancy_not_found")


class StranglerAndOpsTests(PlanServiceTestCase):
    def test_v1_legacy_route_is_served_with_successor_link(self):
        response = self.client.post("/api/v1/plans/", json={"company_description": DESCRIPTION})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["X-API-Version"], "v1")
        self.assertIn("successor-version", response.headers["Link"])
        self.assertIn("/api/v1/plans/", response.headers["Location"])

    def test_taller_02_preview_endpoint_keeps_contract(self):
        response = self.client.post(
            "/api/v2/organizational-plan/", json={"company_description": DESCRIPTION}
        )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["source"], "flask")
        self.assertEqual(body["pattern"], "strangler")
        roots = [d for d in body["proposal"]["departments"] if d["parent_code"] is None]
        self.assertEqual(len(roots), 1)
        self.assertEqual(db.session.query(GenerationRequest).count(), 0)

    def test_public_summary_for_allied_team(self):
        self.create_plan()

        response = self.client.get("/api/v2/public/summary/?limit=2")

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["system"], "JobLab")
        self.assertEqual(body["totals"]["plans"], 1)
        self.assertEqual(len(body["latest_vacancies"]), 2)
        self.assertTrue(body["top_skills"])

    def test_health_and_request_id(self):
        response = self.client.get("/health", headers={"X-Request-ID": "abc-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["checks"]["database"], "ok")
        self.assertEqual(response.headers["X-Request-ID"], "abc-123")

    def test_english_messages_with_accept_language(self):
        response = self.client.post(
            "/api/v2/plans/",
            json={"company_description": "short"},
            headers={"Accept-Language": "en"},
        )

        self.assertEqual(response.headers["Content-Language"], "en")
        self.assertIn("at least 80 characters", response.get_json()["error"]["detail"])
