# fiscal/tests/api/test_ncm_api_isolation.py

import logging
from datetime import date

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework.test import APIClient

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db(transaction=True)


def _get_primary_domain(tenant):
    Domain = apps.get_model("tenants", "Domain")
    dom = Domain.objects.get(tenant=tenant, is_primary=True)
    return dom.domain


@pytest.mark.usefixtures("two_tenants_with_admins")
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", "testserver"],
)
def test_ncm_api_isolamento_por_tenant():
    """
    Garante que a API de NCM respeita o isolamento multi-tenant:

    - GET /fiscal/ncm/ com domínio do tenant1 retorna APENAS NCM do tenant1
    - GET /fiscal/ncm/ com domínio do tenant2 retorna APENAS NCM do tenant2
    """
    Tenant = get_tenant_model()
    User = get_user_model()
    NCM = apps.get_model("fiscal", "NCM")

    tenant1 = Tenant.objects.get(schema_name="99666666000191")
    tenant2 = Tenant.objects.get(schema_name="99777777000191")

    domain1 = _get_primary_domain(tenant1)
    domain2 = _get_primary_domain(tenant2)

    logger.info("Iniciando teste: isolamento de NCM via API entre tenant1 e tenant2.")

    # ------------------------------------------------------------------
    # Cria dados distintos em cada tenant
    # ------------------------------------------------------------------
    with schema_context(tenant1.schema_name):
        admin_t1 = User.objects.create_user(
            username="admin_t1_ncm_iso",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )
        NCM.objects.create(
            codigo="01012100",
            descricao="Cavalos reprodutores - tenant1",
            vigencia_inicio=date(2017, 1, 1),
            ativo=True,
        )
        NCM.objects.create(
            codigo="19053100",
            descricao="Biscoitos doces - tenant1",
            vigencia_inicio=date(2024, 1, 1),
            ativo=True,
        )

    with schema_context(tenant2.schema_name):
        admin_t2 = User.objects.create_user(
            username="admin_t2_ncm_iso",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )
        NCM.objects.create(
            codigo="22030000",
            descricao="Cervejas de malte - tenant2",
            vigencia_inicio=date(2025, 1, 1),
            ativo=True,
        )

    client = APIClient()

    # URL da lista de NCM
    url_list = reverse("fiscal:ncm-list")
    logger.info("DEBUG: reverse('fiscal:ncm-list') = %s", url_list)

    # ------------------------------------------------------------------
    # Consulta como tenant1 (via HTTP_HOST = domain1)
    # ------------------------------------------------------------------
    logger.info("Consultando NCM via API usando domínio do tenant1: %s", domain1)
    client.force_authenticate(user=admin_t1)
    resp_t1 = client.get(url_list, HTTP_HOST=domain1)
    assert resp_t1.status_code == 200, resp_t1.content

    data_t1 = resp_t1.json()
    codigos_t1 = {item["codigo"] for item in data_t1}
    # Deve ver apenas os NCM criados no tenant1
    assert "01012100" in codigos_t1
    assert "19053100" in codigos_t1
    assert "22030000" not in codigos_t1

    # ------------------------------------------------------------------
    # Consulta como tenant2 (via HTTP_HOST = domain2)
    # ------------------------------------------------------------------
    logger.info("Consultando NCM via API usando domínio do tenant2: %s", domain2)
    client.force_authenticate(user=admin_t2)
    resp_t2 = client.get(url_list, HTTP_HOST=domain2)
    assert resp_t2.status_code == 200, resp_t2.content

    data_t2 = resp_t2.json()
    codigos_t2 = {item["codigo"] for item in data_t2}
    # Deve ver apenas os NCM criados no tenant2
    assert "22030000" in codigos_t2
    assert "01012100" not in codigos_t2
    assert "19053100" not in codigos_t2

    logger.info(
        "Fim teste: isolamento de NCM via API confirmado entre tenant1 e tenant2."
    )
