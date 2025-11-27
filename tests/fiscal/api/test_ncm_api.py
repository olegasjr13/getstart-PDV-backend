# fiscal/tests/api/test_ncm_api.py

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

# Precisamos de transação por causa de django-tenants + schema_context
pytestmark = pytest.mark.django_db(transaction=True)


def _get_primary_domain(tenant):
    Domain = apps.get_model("tenants", "Domain")
    dom = Domain.objects.get(tenant=tenant, is_primary=True)
    return dom.domain


def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


@override_settings(
    ROOT_URLCONF="config.urls",   # garante namespace 'fiscal'
    ALLOWED_HOSTS=["*", "testserver"],
)
@pytest.mark.usefixtures("two_tenants_with_admins")
def test_ncm_list_e_busca_por_codigo():
    """
    Garante que a API de NCM:
    - Lista apenas NCM do tenant corrente.
    - Permite busca por código.
    """
    Tenant = get_tenant_model()
    User = get_user_model()
    NCM = apps.get_model("fiscal", "NCM")

    tenant1 = Tenant.objects.get(schema_name="99666666000191")
    domain1 = _get_primary_domain(tenant1)

    logger.info("Iniciando teste: consulta NCM via API no tenant1.")

    # Criamos o usuário e os NCM dentro do schema do tenant1
    with schema_context(tenant1.schema_name):
        admin_t1 = User.objects.create_user(
            username="admin_t1_ncm",
            password="senha123",
            is_staff=True,
            is_superuser=True,
        )

        NCM.objects.create(
            codigo="01012100",
            descricao="Cavalos reprodutores de raça pura",
            vigencia_inicio=date(2017, 1, 1),
            ativo=True,
        )
        NCM.objects.create(
            codigo="01012900",
            descricao="Outros cavalos",
            vigencia_inicio=date(2017, 1, 1),
            ativo=True,
        )

    # Usa APIClient do DRF para evitar sessão (django_session)
    client = APIClient()
    client.force_authenticate(user=admin_t1)

    # URL resolvida via reverse, garantindo que bate no router correto
    # Nome da rota vem do router: ncm-list (list action do ViewSet)
    url_list = reverse("fiscal:ncm-list")
    logger.info("DEBUG: reverse('fiscal:ncm-list') = %s", url_list)

    # Lista geral no tenant1
    resp = client.get(
        url_list,
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 200, resp.content
    results = extract_results(resp.json())
    codigos = {item["codigo"] for item in results}
    assert "01012100" in codigos
    assert "01012900" in codigos

    # Busca por código exato (via search)
    resp = client.get(
        f"{url_list}?search=01012100",
        HTTP_HOST=domain1,
    )
    assert resp.status_code == 200, resp.content
    results = extract_results(resp.json())
    assert any(item["codigo"] == "01012100" for item in results)

    logger.info("Fim teste: NCM consultado com sucesso via API.")
