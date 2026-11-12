from django.contrib import admin
from django.urls import include, path

from joblab.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/v1/", include("organization.api.urls")),
    path("", include("organization.urls")),
]
