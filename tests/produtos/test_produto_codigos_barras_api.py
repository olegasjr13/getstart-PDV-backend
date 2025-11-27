# produtos/tests/api/test_produto_codigos_barras_api.py

import logging
from decimal import Decimal

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


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_produto_codigo_barras_nao_vaza_entre_tenants(client):
    """
    Código de barras criado no tenant1 não é visível no tenant2.
    """
    Tenant = get_tenant_model()
    User = get_user_model()

    tenant1 = Tenant.objects.get(schema_name="99666666000191")
    tenant2 = Tenant.objects.get(schema_name="99777777000191")

    domain1 = _get_primary_domain(tenant1)
    domain2 = _get_primary_domain(tenant2)

    Produto = apps.get_model("produtos", "Produto")
    GrupoProduto = apps.get_model("produtos", "GrupoProduto")
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")
    NCM = apps.get_model("fiscal", "NCM")
    ProdutoCodigoBarras = apps.get_model("produtos", "ProdutoCodigoBarras")

    logger.info(
        "Iniciando teste: códigos de barras isolados por tenant."
    )

    with schema_context(tenant1.schema_name):
        admin_t1 = User.objects.create_user(
            username="admin_t1_bar",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )

        grupo = GrupoProduto.objects.create(
            nome="Bebidas",
            descricao="Grupo bebidas",
            ativo=True,
        )
        un = UnidadeMedida.objects.create(
            sigla="UN",
            descricao="Unidade",
            fator_conversao=Decimal("1.000000"),
        )
        ncm = NCM.objects.create(
            codigo="22030000",
            descricao="Cervejas de malte",
            ativo=True,
        )

        prod = Produto.objects.create(
            codigo_interno="PROD001",
            descricao="Cerveja Lata",
            grupo=grupo,
            ncm=ncm,
            unidade_comercial=un,
            unidade_tributavel=un,
            fator_conversao_tributavel=Decimal("1.000000"),
            aliquota_icms=Decimal("18.00"),
        )

    client.force_login(admin_t1)

    payload = {
        "produto": str(prod.id),
        "codigo": "7891234567890",
        "tipo_barra": "EAN13",
        "funcao": "COMERCIAL",
        "principal": True,
        "ativo": True,
    }

    resp = client.post(
        "/api/v1/produtos/produtos-codigos-barras/",
        payload,
        content_type="application/json",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 201, resp.content
    cb_id = resp.json()["id"]

    # Tenant1 enxerga
    resp = client.get(
        f"/api/v1/produtos/produtos-codigos-barras/{cb_id}/",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 200
    assert resp.json()["codigo"] == "7891234567890"

    # Tenant2 não deve enxergar esse código de barras
    resp = client.get(
        f"/api/v1/produtos/produtos-codigos-barras/{cb_id}/",
        HTTP_HOST=domain2,
    )
    # Pode ser 404 (melhor cenário) ou 403/401 dependendo da config de auth
    assert resp.status_code in (404, 403, 401)

    with schema_context(tenant2.schema_name):
        assert not ProdutoCodigoBarras.objects.filter(codigo="7891234567890").exists()

    logger.info("Fim teste: código de barras não vaza entre tenants.")
