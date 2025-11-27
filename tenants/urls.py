# tenants/urls.py
from django.urls import path
from .views.tenants_views import criar_tenant

urlpatterns = [
    # Endpoint público de provisionamento de tenant
    path(
        "criar-tenant/",
        criar_tenant,
        name="criar-tenant",
    ),
    path("criar-tenant", criar_tenant),
]
