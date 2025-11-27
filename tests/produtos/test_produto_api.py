# produtos/tests/api/test_produto_api.py

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


def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_admin_tenant1_cria_produto_usando_ncm_e_unidades(client):
    """
    Admin do tenant1 cria produto com NCM + unidades.
    - Produto só existe no schema do tenant1.
    """
    Tenant = get_tenant_model()
    User = get_user_model()

    tenant1 = Tenant.objects.get(schema_name="99666666000191")
    domain1 = _get_primary_domain(tenant1)

    GrupoProduto = apps.get_model("produtos", "GrupoProduto")
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")
    NCM = apps.get_model("fiscal", "NCM")
    Produto = apps.get_model("produtos", "Produto")

    logger.info(
        "Iniciando teste: admin do tenant1 criando produto completo "
        "(grupo, NCM, unidades)."
    )

    # Cria dados de apoio dentro do schema do tenant1
    with schema_context(tenant1.schema_name):
        admin_t1 = User.objects.create_user(
            username="admin_t1_prod",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )

        grupo = GrupoProduto.objects.create(
            nome="Bebidas",
            descricao="Grupo bebidas",
            ativo=True,
        )
        un_com = UnidadeMedida.objects.create(
            sigla="UN",
            descricao="Unidade",
            fator_conversao=Decimal("1.000000"),
        )
        un_tri = UnidadeMedida.objects.create(
            sigla="CX",
            descricao="Caixa",
            fator_conversao=Decimal("12.000000"),
        )
        ncm = NCM.objects.create(
            codigo="22030000",
            descricao="Cervejas de malte",
            ativo=True,
        )

    client.force_login(admin_t1)

    payload = {
        "codigo_interno": "PROD001",
        "descricao": "Cerveja Lata 350ml",
        "descricao_complementar": "Cerveja Pilsen",
        "grupo": str(grupo.id),
        "ncm": str(ncm.id),
        "unidade_comercial": str(un_com.id),
        "unidade_tributavel": str(un_tri.id),
        "fator_conversao_tributavel": "12.000000",
        "aliquota_icms": "18.00",
        "aliquota_pis": "1.65",
        "aliquota_cofins": "7.60",
        "permite_fracionar": False,
        "rastreavel": False,
        "ativo": True,
    }

    resp = client.post(
        "/api/v1/produtos/produtos/",
        payload,
        content_type="application/json",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 201, resp.content
    produto_id = resp.json()["id"]

    # Garantir que foi criado no schema do tenant1
    with schema_context(tenant1.schema_name):
        assert Produto.objects.filter(id=produto_id).exists()

    logger.info("Fim teste: produto criado com sucesso no tenant1.")
