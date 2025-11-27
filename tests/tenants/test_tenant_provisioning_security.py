# tenants/tests/test_tenant_provisioning_security.py

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from commons.tests.helpers import _bootstrap_public_tenant_and_domain
from django.db import connection


def _build_payload_tenant_valido():
    """
    Payload mínimo e válido para criação de tenant.

    Usamos CNPJs específicos deste arquivo para evitar colisão com
    outros testes (inclusive os de provisioning).
    """
    return {
        "cnpj_raiz": "99333333000191",
        "nome": "Empresa Segurança LTDA",
        "domain": "tenant-99333333000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Empresa Segurança LTDA",
            "nome_fantasia": "Loja Segurança",
            "cnpj": "99333333000109",
            "endereco": {
                "pais": {
                    "codigo_nfe": "1058",
                    "nome": "BRASIL",
                    "sigla2": "BR",
                    "sigla3": "BRA",
                },
                "uf": {
                    "sigla": "SP",
                    "nome": "São Paulo",
                    "codigo_ibge": "35",
                    "pais": {
                        "codigo_nfe": "1058",
                        "nome": "BRASIL",
                        "sigla2": "BR",
                        "sigla3": "BRA",
                    },
                },
                "municipio": {
                    "nome": "São Paulo",
                    "codigo_ibge": "3550308",
                    "codigo_siafi": "7107",
                },
                "bairro": "Centro",
                "logradouro_tipo": "RUA",
                "logradouro_nome": "Paulista",
                "logradouro_cep": "01311000",
                "numero": "100",
                "complemento": "",
                "referencia": "",
                "cep": "01311000",
            },
        },
    }


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-seguro",
)
def test_criar_tenant_sem_token_retorna_403():
    """
    Segurança: criação de tenant SEM cabeçalho de token deve ser bloqueada.

    - Não envia HTTP_X_TENANT_PROVISIONING_TOKEN
    - Espera 403 (ou 401, dependendo da implementação – mas 403 é mais comum).
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    payload = _build_payload_tenant_valido()

    resp = client.post(url, data=payload, format="json")  # sem header de token

    assert resp.status_code in (401, 403), resp.content


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-seguro",
)
def test_criar_tenant_com_token_incorreto_retorna_403():
    """
    Segurança: criação de tenant com token inválido deve ser bloqueada.

    - Envia HTTP_X_TENANT_PROVISIONING_TOKEN errado
    - Espera 403 / 401
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    payload = _build_payload_tenant_valido()

    headers = {
        # Token errado
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "token-invalido",
    }

    resp = client.post(url, data=payload, format="json", **headers)

    assert resp.status_code in (401, 403), resp.content


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-seguro",
)
def test_criar_tenant_com_metodo_get_retorna_405():
    """
    Segurança / RESTfulness:
    - O endpoint de criação de tenant deve aceitar apenas POST.
    - GET deve retornar 405 Method Not Allowed (ou, no mínimo, != 2xx).
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")

    resp = client.get(url)

    # Se estiver corretamente restrito a POST, o padrão DRF é 405
    assert resp.status_code in (401, 403, 405), resp.content
