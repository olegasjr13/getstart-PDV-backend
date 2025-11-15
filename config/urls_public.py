# config/urls_public.py (public schema)
from django.urls import path, include
urlpatterns = [
    path("api/v1/", include("commons.urls")),
    path("api/v1/", include("tenants.urls")),  
]
