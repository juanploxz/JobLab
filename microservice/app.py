from __future__ import annotations

import re
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)


def _normalize_description(company_description: str) -> str:
    return " ".join(company_description.split())


def _infer_company_name(description: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9ÁÉÍÓÚáéíóúÑñ\s]", " ", description)
    tokens = [token for token in cleaned.split() if len(token) > 3]
    if len(tokens) >= 2:
        return " ".join(tokens[:2]).title()
    if tokens:
        return tokens[0].title()
    return "Empresa Demo"


def _build_departments(description: str) -> list[dict[str, Any]]:
    text = description.lower()

    if "software" in text or "tecnolog" in text or "digital" in text:
        departments = [
            {"code": "ROOT", "name": "Dirección General", "description": "Establece la visión, objetivos y prioridades del negocio.", "parent_code": None},
            {"code": "ENG", "name": "Ingeniería", "description": "Desarrolla y mantiene la plataforma digital y los servicios del negocio.", "parent_code": "ROOT"},
            {"code": "OPS", "name": "Operaciones", "description": "Asegura ejecución, calidad y continuidad de la operación diaria.", "parent_code": "ROOT"},
            {"code": "SALES", "name": "Ventas y Comercial", "description": "Conecta la oferta con clientes, alianzas y crecimiento del negocio.", "parent_code": "ROOT"},
        ]
    else:
        departments = [
            {"code": "ROOT", "name": "Dirección General", "description": "Define la estrategia y la dirección del negocio.", "parent_code": None},
            {"code": "OPS", "name": "Operaciones", "description": "Ejecución operativa, calidad y continuidad del modelo de negocio.", "parent_code": "ROOT"},
            {"code": "SALES", "name": "Ventas", "description": "Genera demanda, atención al cliente y crecimiento comercial.", "parent_code": "ROOT"},
            {"code": "HR", "name": "Talento y Cultura", "description": "Asegura reclutamiento, formación y experiencia del equipo.", "parent_code": "ROOT"},
        ]

    return departments


def _build_vacancies(description: str) -> list[dict[str, Any]]:
    text = description.lower()
    if "software" in text or "tecnolog" in text or "digital" in text:
        return [
            {
                "department_code": "ENG",
                "name": "Software Engineer",
                "available_positions": 2,
                "salary_min": 4500000,
                "salary_max": 7000000,
                "currency": "COP",
                "salary_period": "MONTHLY",
                "description": "Diseña, desarrolla y mantiene soluciones digitales para la operación del negocio.",
                "required_knowledge": ["Python", "APIs", "Arquitectura de software"],
                "reports_to": "ROOT",
            },
            {
                "department_code": "OPS",
                "name": "Operations Analyst",
                "available_positions": 1,
                "salary_min": 3500000,
                "salary_max": 5200000,
                "currency": "COP",
                "salary_period": "MONTHLY",
                "description": "Monitorea procesos, indicadores y ejecución operativa del negocio.",
                "required_knowledge": ["Excel", "Indicadores", "Procesos"],
                "reports_to": "ROOT",
            },
        ]

    return [
        {
            "department_code": "OPS",
            "name": "Operations Coordinator",
            "available_positions": 1,
            "salary_min": 3000000,
            "salary_max": 4500000,
            "currency": "COP",
            "salary_period": "MONTHLY",
            "description": "Coordina la operación y la continuidad del proceso productivo.",
            "required_knowledge": ["Procesos", "Gestión", "Indicadores"],
            "reports_to": "ROOT",
        },
        {
            "department_code": "SALES",
            "name": "Commercial Representative",
            "available_positions": 1,
            "salary_min": 3200000,
            "salary_max": 5000000,
            "currency": "COP",
            "salary_period": "MONTHLY",
            "description": "Acompaña clientes, negocia ventas y fortalece la presencia comercial.",
            "required_knowledge": ["Ventas", "Clientes", "Comunicación"],
            "reports_to": "ROOT",
        },
    ]


@app.get("/")
def index() -> Any:
    return jsonify({
        "service": "joblab-strangler-microservice",
        "version": "v2",
        "status": "ok",
        "pattern": "strangler",
        "legacy_target": "django",
        "routes": [
            "/health",
            "/api/v2/organizational-plan/",
        ],
    })


@app.get("/health")
def health() -> Any:
    return jsonify({
        "status": "ok",
        "service": "joblab-strangler-microservice",
        "version": "v2",
        "pattern": "strangler",
    })


@app.post("/api/v2/organizational-plan/")
def generate_organizational_plan() -> Any:
    payload = request.get_json(silent=True) or {}
    company_description = payload.get("company_description")

    if not isinstance(company_description, str) or not company_description.strip():
        return jsonify({
            "error": {
                "code": "invalid_company_description",
                "detail": "Debe enviar company_description como texto no vacio.",
            }
        }), 400

    normalized = _normalize_description(company_description)
    if len(normalized) < 80:
        return jsonify({
            "error": {
                "code": "company_description_too_short",
                "detail": "La descripcion debe tener al menos 80 caracteres.",
            }
        }), 400

    company_name = _infer_company_name(normalized)
    proposal = {
        "company_name": company_name,
        "company_summary": (
            f"Modelo de estructura organizacional propuesta para {company_name}, "
            "generada desde el microservicio encargado de la migración gradual del negocio."
        ),
        "assumptions": [
            "La empresa se encuentra en etapa de crecimiento y requiere una estructura simple pero escalable.",
            "La operación prioriza calidad, velocidad y claridad de responsabilidades.",
        ],
        "departments": _build_departments(normalized),
        "vacancies": _build_vacancies(normalized),
    }

    return jsonify({
        "message": "Plan organizacional generado por el microservicio estrangulador",
        "source": "flask",
        "pattern": "strangler",
        "company_description": normalized,
        "proposal": proposal,
    })


@app.errorhandler(404)
def not_found(_error: Any) -> Any:
    return jsonify({
        "error": {
            "code": "not_found",
            "detail": "Recurso no encontrado.",
        }
    }), 404


@app.errorhandler(500)
def internal_error(_error: Any) -> Any:
    return jsonify({
        "error": {
            "code": "internal_server_error",
            "detail": "El microservicio no pudo procesar la solicitud.",
        }
    }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
