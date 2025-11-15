from django.urls import path
from .views.tenants_views import criar_tenant

urlpatterns = [
    path("tenants", criar_tenant),  # POST /api/v1/tenants
]
