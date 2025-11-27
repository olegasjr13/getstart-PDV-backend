# config/urls_public.py
from django.urls import path, include

urlpatterns = [
    path("api/v1/commons/", include("commons.urls")),
    path(
        "api/v1/tenants/",
        include(("tenants.urls", "tenants"), namespace="tenants"),
    ),
]
