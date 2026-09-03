from django.urls import path

from organization.api_views import GenerateOrganizationAPIView
from organization.views import (
    GenerateOrganizationView,
    GenerationHistoryView,
    OrganizationalPlanDetailView,
)

app_name = "organization"

urlpatterns = [
    path("", GenerateOrganizationView.as_view(), name="generate"),
    path("planes/", GenerationHistoryView.as_view(), name="history"),
    path("planes/<int:pk>/", OrganizationalPlanDetailView.as_view(), name="detail"),
    path("api/v1/generate/", GenerateOrganizationAPIView.as_view(), name="api-generate-organization"),
]