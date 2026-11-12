from django.urls import path

from organization.views import (
    ActivityView,
    AllyView,
    GenerateOrganizationView,
    GenerationHistoryView,
    OrganizationalPlanDetailView,
    ReportDownloadView,
    ReportStatusView,
    RequestReportView,
    SystemStatusView,
)

app_name = "organization"

urlpatterns = [
    path("", GenerateOrganizationView.as_view(), name="generate"),
    path("planes/", GenerationHistoryView.as_view(), name="history"),
    path("planes/<int:pk>/", OrganizationalPlanDetailView.as_view(), name="detail"),
    path("planes/<int:pk>/reporte/", RequestReportView.as_view(), name="request-report"),
    path("reportes/<str:task_id>/", ReportStatusView.as_view(), name="report-status"),
    path("reportes/<str:task_id>/descargar/", ReportDownloadView.as_view(), name="report-download"),
    path("aliados/", AllyView.as_view(), name="ally"),
    path("actividad/", ActivityView.as_view(), name="activity"),
    path("estado/", SystemStatusView.as_view(), name="status"),
]
