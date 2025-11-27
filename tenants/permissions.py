# tenants/permissions.py
import logging

from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.permissions import BasePermission

logger = logging.getLogger("pdv.tenants")


class PublicProvisioningPermission(BasePermission):
    """
    Permite provisionamento de tenant via endpoint público.

    Regras:
      - Requisição PRECISA estar no schema público (public).
      - Requer um token estático no header:
          X-Admin-Token OU X-Tenant-Provisioning-Token
      - O token deve bater com ADMIN_PROVISIONING_TOKEN ou
        TENANT_PROVISIONING_TOKEN do settings.
    """

    message = "Você não tem permissão para executar essa ação."

    def has_permission(self, request, view) -> bool:
        schema_name = getattr(connection, "schema_name", None)
        public_schema = get_public_schema_name()

        # 1) Só aceita chamadas feitas no schema público
        if schema_name != public_schema:
            logger.warning(
                "public_provisioning_permission_denied_schema",
                extra={
                    "reason": "not_public_schema",
                    "current_schema": schema_name,
                    "expected_schema": public_schema,
                    "path": request.path,
                    "method": request.method,
                },
            )
            return False

        # 2) Valida token de provisionamento no header
        header_token = (
            request.headers.get("X-Admin-Token")
            or request.headers.get("X-Tenant-Provisioning-Token")
        )
        env_token = (
            getattr(settings, "ADMIN_PROVISIONING_TOKEN", None)
            or getattr(settings, "TENANT_PROVISIONING_TOKEN", None)
        )

        if not header_token:
            logger.warning(
                "public_provisioning_permission_denied_no_header_token",
                extra={
                    "reason": "missing_header_token",
                    "path": request.path,
                    "method": request.method,
                },
            )
            return False

        if not env_token:
            logger.error(
                "public_provisioning_permission_denied_no_env_token",
                extra={
                    "reason": "missing_env_token",
                    "path": request.path,
                    "method": request.method,
                },
            )
            return False

        if header_token != env_token:
            logger.warning(
                "public_provisioning_permission_denied_invalid_token",
                extra={
                    "reason": "invalid_token",
                    "path": request.path,
                    "method": request.method,
                },
            )
            return False

        logger.info(
            "public_provisioning_permission_granted",
            extra={
                "schema": schema_name,
                "path": request.path,
                "method": request.method,
            },
        )
        return True
