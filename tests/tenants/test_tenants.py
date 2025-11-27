import pytest
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework.test import APIClient
from tenants.models.tenants_models import Tenant

@pytest.mark.django_db
def test_criar_tenant_via_url():
    client = APIClient()

    payload = {
        "schema_name": "tenant_teste",
        "cnpj_raiz": "12345678000199",
        "nome": "Empresa de Teste",
        "premium_db_alias": "default",
        "active": True
    }

    # Usa o schema público explicitamente
    public_schema = get_public_schema_name()
    with schema_context(public_schema):
        # Certifique-se de que o URLConf do public schema é usado
        response = client.post("/api/v1/tenants/criar-tenant/", payload, format="json")

    assert response.status_code == 201, response.content

    data = response.json()
    assert data["nome"] == "Empresa de Teste"
    assert data["cnpj_raiz"] == "12345678000199"
    assert data["schema_name"] == "tenant_teste"
    assert data["premium_db_alias"] == "default"
    assert data["active"] is True

    # Confirma que existe no banco
    assert Tenant.objects.count() == 1
    tenant = Tenant.objects.first()
    assert tenant.nome == "Empresa de Teste"
