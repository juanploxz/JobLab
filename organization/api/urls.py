from django.urls import path

from organization.api.views import (
    PlanCollectionAPIView,
    PlanDetailAPIView,
    PlanVacancyCollectionAPIView,
    PlanVacancyDetailAPIView,
)

app_name = "organization_api"

urlpatterns = [
    path("plans/", PlanCollectionAPIView.as_view(), name="plan-list-create"),
    path("plans/<int:pk>/", PlanDetailAPIView.as_view(), name="plan-detail"),
    path(
        "plans/<int:pk>/vacancies/",
        PlanVacancyCollectionAPIView.as_view(),
        name="plan-vacancy-create",
    ),
    path(
        "plans/<int:pk>/vacancies/<int:vacancy_pk>/",
        PlanVacancyDetailAPIView.as_view(),
        name="plan-vacancy-detail",
    ),
]
