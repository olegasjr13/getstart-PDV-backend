# commons/tests/helpers.py
from django.apps import apps
from django.db import connection
from django_tenants.utils import (
    get_tenant_model,
    get_public_schema_name,
)

TENANT_SCHEMA = "12345678000191"
TENANT_HOST = "cliente-demo.localhost"


def _bootstrap_public_tenant_and_domain():
    """
    Garante que:
      - Tenant 'public' existe
      - Tenant TENANT_SCHEMA existe
      - Domains principais existem e apontam para os tenants corretos:

          - 'localhost', '127.0.0.1', 'testserver' → tenant público
          - TENANT_HOST (ex: cliente-demo.localhost) → tenant de teste

    Essa função deve ser segura para ser chamada várias vezes (idempotente).
    """

    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    public_schema = get_public_schema_name()

    # Sempre garante que estamos no schema público ao criar tenants/domínios
    connection.set_schema_to_public()

    # 1) Tenant público
    public_tenant, _ = Tenant.objects.get_or_create(
        schema_name=public_schema,
        defaults={
            "cnpj_raiz": "00000000000000",
            "nome": "PUBLIC",
            "premium_db_alias": None,
        },
    )

    # 2) Tenant de testes existente (para os testes fiscais etc.)
    tenant_teste, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults={
            "cnpj_raiz": TENANT_SCHEMA,
            "nome": "Tenant Teste",
            "premium_db_alias": None,
        },
    )

    # 3) Domains que devem apontar para o tenant PÚBLICO
    public_hosts = ("localhost", "127.0.0.1", "testserver")
    for host in public_hosts:
        dom, created = Domain.objects.get_or_create(
            domain=host,
            defaults={
                "tenant": public_tenant,
                "is_primary": host == "localhost",
            },
        )
        # Se já existe mas aponta pra outro tenant, força corrigir
        if not created and dom.tenant_id != public_tenant.id:
            dom.tenant = public_tenant
            # Mantém is_primary só se já era ou se for localhost
            dom.is_primary = dom.is_primary or (host == "localhost")
            dom.save(update_fields=["tenant", "is_primary"])

    # 4) Domain principal para o tenant de testes (usado nos testes fiscais)
    dom_teste, created = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults={
            "tenant": tenant_teste,
            "is_primary": True,
        },
    )
    if not created and dom_teste.tenant_id != tenant_teste.id:
        dom_teste.tenant = tenant_teste
        dom_teste.is_primary = True
        dom_teste.save(update_fields=["tenant", "is_primary"])
