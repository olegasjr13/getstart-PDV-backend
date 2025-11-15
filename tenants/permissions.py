# tenants/permissions.py
from rest_framework.permissions import BasePermission
from django.conf import settings

class PublicProvisioningPermission(BasePermission):
    """
    Permite provisionamento de tenant via token estático de ambiente.
    Aceita X-Admin-Token ou X-Tenant-Provisioning-Token no header.
    Compara com ADMIN_PROVISIONING_TOKEN ou TENANT_PROVISIONING_TOKEN do settings.
    """

    def has_permission(self, request, view):
        header_token = (
            request.headers.get("X-Admin-Token")
            or request.headers.get("X-Tenant-Provisioning-Token")
        )
        env_token = (
            getattr(settings, "ADMIN_PROVISIONING_TOKEN", None)
            or getattr(settings, "TENANT_PROVISIONING_TOKEN", None)
        )
        return bool(header_token and env_token and header_token == env_token)
