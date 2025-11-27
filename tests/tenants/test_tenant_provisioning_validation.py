# tenants/tests/test_tenant_provisioning_validation.py

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from commons.tests.helpers import _bootstrap_public_tenant_and_domain
from django.db import connection


def _build_payload_basico():
    """
    Payload base e válido, que será alterado nos testes para validar cenários
    de erro.
    """
    return {
        "cnpj_raiz": "99444444000191",
        "nome": "Empresa Validação LTDA",
        "domain": "tenant-99444444000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Empresa Validação LTDA",
            "nome_fantasia": "Loja Validação",
            "cnpj": "99444444000109",
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
                "numero": "10",
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
    TENANT_PROVISIONING_TOKEN="test-token-validacao",
)
def test_criar_tenant_sem_filial_retorna_400():
    """
    Validação: não deve ser possível criar tenant sem o bloco 'filial'.

    - Remove a chave 'filial' do payload.
    - Espera status 400 (Bad Request).
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token-validacao",
    }

    payload = _build_payload_basico()
    payload.pop("filial")

    resp = client.post(url, data=payload, format="json", **headers)

    assert resp.status_code == 400, resp.content


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-validacao",
)
def test_criar_tenant_sem_cnpj_raiz_retorna_400():
    """
    Validação: o campo 'cnpj_raiz' é obrigatório para formar o schema_name.

    - Remove a chave 'cnpj_raiz'.
    - Espera 400.
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token-validacao",
    }

    payload = _build_payload_basico()
    payload.pop("cnpj_raiz")

    resp = client.post(url, data=payload, format="json", **headers)

    assert resp.status_code == 400, resp.content


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-validacao",
)
def test_criar_tenant_com_cnpj_filial_invalido_retorna_400():
    """
    Validação: CNPJ da filial com formato inválido / string inválida
    deve ser rejeitado (se a view/serializer estiver validando CNPJ).

    - Define um CNPJ totalmente inválido (ex: '123').
    - Espera 400 (caso esteja validando CNPJ).
    """
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token-validacao",
    }

    payload = _build_payload_basico()
    payload["filial"]["cnpj"] = "123"  # cnpj totalmente inválido

    resp = client.post(url, data=payload, format="json", **headers)

    # Se ainda não houver validação de CNPJ, esse teste vai falhar
    # e servirá como guia para implementar a regra.
    assert resp.status_code == 400, resp.content
