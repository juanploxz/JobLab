from django.contrib import admin

from organization.models import (
    OrganizationalPlan,
    OrganizationalUnit,
    OrganizationGenerationRequest,
    Vacancy,
)


@admin.register(OrganizationGenerationRequest)
class OrganizationGenerationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "provider_name", "created_at", "completed_at")
    list_filter = ("status", "provider_name")
    search_fields = ("company_description",)
    readonly_fields = ("created_at", "completed_at")


class OrganizationalUnitInline(admin.TabularInline):
    model = OrganizationalUnit
    extra = 0


class VacancyInline(admin.TabularInline):
    model = Vacancy
    extra = 0


@admin.register(OrganizationalPlan)
class OrganizationalPlanAdmin(admin.ModelAdmin):
    list_display = ("company_name", "review_status", "created_at")
    list_filter = ("review_status",)
    search_fields = ("company_name", "company_summary")
    inlines = (OrganizationalUnitInline, VacancyInline)


@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "plan", "parent")
    list_filter = ("plan",)
    search_fields = ("name", "code")


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "available_positions", "currency", "status")
    list_filter = ("status", "currency", "salary_period")
    search_fields = ("name", "description")
