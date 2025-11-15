from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django_tenants.utils import get_tenant_model
from django.core.management import call_command
from django.apps import apps
from tenants.permissions import PublicProvisioningPermission
from tenants.serializers import TenantCreateSerializer

@api_view(["POST"])
@authentication_classes([])
@permission_classes([PublicProvisioningPermission]) 
def criar_tenant(request):
    ser = TenantCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain") 

    tenant = Tenant(
        schema_name=data["cnpj_raiz"],
        cnpj_raiz=data["cnpj_raiz"],
        nome=data["nome"],
        premium_db_alias=data.get("premium_db_alias") or None
    )
    tenant.save()  # cria schema

    # Migrar apps do tenant
    call_command(
        "migrate_schemas",
        tenant=True,
        schema_name=tenant.schema_name,
        interactive=False,
        verbosity=0
    )

    Domain.objects.create(
        domain=data["domain"],
        tenant=tenant,
        is_primary=True
    )

    return Response(
        {"tenant": tenant.cnpj_raiz, "schema": tenant.schema_name},
        status=status.HTTP_201_CREATED
    )
