import unittest

from app import app


class OrganizationalPlanEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_generates_json_plan_for_valid_description(self) -> None:
        response = self.client.post(
            "/api/v2/organizational-plan/",
            json={
                "company_description": (
                    "Somos una empresa de software que desarrolla productos digitales "
                    "para PYMES y necesita una estructura clara para ingeniería, "
                    "operaciones y ventas."
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        payload = response.get_json()
        self.assertEqual(payload["source"], "flask")
        self.assertEqual(payload["pattern"], "strangler")
        self.assertEqual(payload["proposal"]["departments"][0]["code"], "ROOT")
        self.assertTrue(payload["proposal"]["vacancies"])

    def test_rejects_missing_description(self) -> None:
        response = self.client.post(
            "/api/v2/organizational-plan/",
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "invalid_company_description",
        )

    def test_rejects_short_description(self) -> None:
        response = self.client.post(
            "/api/v2/organizational-plan/",
            json={"company_description": "Empresa corta"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "company_description_too_short",
        )


if __name__ == "__main__":
    unittest.main()
