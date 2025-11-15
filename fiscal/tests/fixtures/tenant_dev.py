# fiscal/tests/fixtures/tenant_dev.py
import pytest
from django.db import transaction
from django.core.management import call_command
from django.apps import apps

TENANT_CNPJ = "12345678000199"
TENANT_DOMAIN = "cliente-demo.localhost"

@pytest.fixture(scope="session", autouse=True)
def ensure_dev_tenant_and_domain(django_db_setup, django_db_blocker):
    """
    Antes de QUALQUER teste:
    - Cria (ou garante) o tenant 12345678000199 no PUBLIC do BANCO DE TESTES
    - Cria (ou garante) o Domain cliente-demo.localhost -> esse tenant
    - Roda migrações do schema do tenant no BANCO DE TESTES
    """
    with django_db_blocker.unblock():
        Tenant = apps.get_model("tenants", "Tenant")
        Domain = apps.get_model("tenants", "Domain")

        with transaction.atomic():
            t, _ = Tenant.objects.get_or_create(
                schema_name=TENANT_CNPJ,
                defaults={
                    "cnpj_raiz": TENANT_CNPJ,
                    "nome": "Cliente Demo",
                    "premium_db_alias": None,
                }
            )

            d, created = Domain.objects.get_or_create(
                domain=TENANT_DOMAIN,
                defaults={"tenant": t, "is_primary": True},
            )
            if d.tenant_id != t.id:
                d.tenant = t
                d.is_primary = True
                d.save(update_fields=["tenant", "is_primary"])

        # Aplica migrações do SCHEMA DO TENANT no banco de testes
        call_command(
            "migrate_schemas",
            tenant=True,
            schema_name=TENANT_CNPJ,
            interactive=False,
            verbosity=0,
        )
