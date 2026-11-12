"""Gateways (ports + adapters) through which Django reaches the extracted microservices.

Strangler pattern: the HTML front end depends on the ``PlanGateway`` port. The
``LocalPlanGateway`` adapter keeps the legacy in-process Service Layer as a
fallback, while ``HttpPlanGateway`` routes every use case to ``plan-service``.
The adapter is chosen by configuration (``PLAN_SERVICE_URL``), so the migration
can be rolled back without touching views or templates.
"""
