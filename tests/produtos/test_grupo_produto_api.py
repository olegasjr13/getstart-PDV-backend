# produtos/tests/api/test_grupo_produto_api.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db(transaction=True)


def _get_primary_domain(tenant):
    Domain = apps.get_model("tenants", "Domain")
    dom = Domain.objects.get(tenant=tenant, is_primary=True)
    return dom.domain


def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_admin_tenant1_cria_grupo_visivel_so_no_tenant1(two_tenants_with_admins):
    """
    Admin do tenant1 cria grupo de produtos.
    - Deve aparecer no tenant1.
    - Não deve aparecer no tenant2.
    """
    Tenant = get_tenant_model()
    User = get_user_model()
    GrupoProduto = apps.get_model("produtos", "GrupoProduto")

    tenant1 = Tenant.objects.get(schema_name="99666666000191")
    tenant2 = Tenant.objects.get(schema_name="99777777000191")

    domain1 = _get_primary_domain(tenant1)
    domain2 = _get_primary_domain(tenant2)

    logger.info(
        "Iniciando teste: admin do tenant1 criando grupo, "
        "visível apenas no tenant1."
    )

    # Cria admin dentro do schema do tenant1
    with schema_context(tenant1.schema_name):
        admin_t1 = User.objects.create_user(
            username="admin_t1_grupo",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )

    client.force_login(admin_t1)

    payload = {
        "nome": "Bebidas",
        "descricao": "Grupo de bebidas em geral",
        "ativo": True,
    }

    # Criação via domínio do tenant1
    resp = client.post(
        "/api/v1/produtos/grupos-produtos/",
        payload,
        content_type="application/json",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 201, resp.content
    grupo_id = resp.json()["id"]

    # Lista no tenant1 deve retornar o grupo
    resp = client.get(
        "/api/v1/produtos/grupos-produtos/",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 200
    results_t1 = extract_results(resp.json())
    assert any(str(g["id"]) == str(grupo_id) for g in results_t1)

    # No tenant2, esse grupo não existe
    resp = client.get(
        "/api/v1/produtos/grupos-produtos/",
        HTTP_HOST=domain2,
    )
    assert resp.status_code in (200, 403, 401)
    if resp.status_code == 200:
        results_t2 = extract_results(resp.json())
        assert all(str(g["nome"]) != "Bebidas" for g in results_t2)

    # Garantia extra por schema_context
    with schema_context(tenant2.schema_name):
        assert not GrupoProduto.objects.filter(nome="Bebidas").exists()

    logger.info("Fim teste: grupo criado no tenant1 não aparece no tenant2.")
