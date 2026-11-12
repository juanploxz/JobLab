import unittest

from plan_service import create_app
from plan_service.extensions import db
from plan_service.infra.events import InMemoryEventPublisher

DESCRIPTION = (
    "Somos una empresa de software en Medellin que desarrolla una plataforma para "
    "pequenas tiendas y necesita definir su equipo inicial de producto, operaciones y ventas."
)


class PlanServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.events = InMemoryEventPublisher()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "AI_PROVIDER": "MOCK",
                "EVENT_PUBLISHER": self.events,
            }
        )
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def create_plan(self) -> dict:
        response = self.client.post("/api/v2/plans/", json={"company_description": DESCRIPTION})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    @staticmethod
    def vacancy_payload(department_id: int) -> dict:
        return {
            "department_id": department_id,
            "name": "Arquitecto de Integraciones",
            "available_positions": 1,
            "salary_min": "6500000.00",
            "salary_max": "8500000.00",
            "currency": "COP",
            "salary_period": "MONTHLY",
            "description": (
                "Disena integraciones confiables, documenta contratos y mantiene "
                "pruebas automatizadas de los servicios empresariales."
            ),
            "required_knowledge": ["Python", "Flask"],
            "reports_to": "Lider Tecnico",
        }
