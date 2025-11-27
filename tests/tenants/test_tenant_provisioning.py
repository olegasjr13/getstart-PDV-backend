# tenants/tests/test_tenant_provisioning.py

import logging

import pytest
from django.apps import apps
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework.test import APIClient

from commons.tests.helpers import _bootstrap_public_tenant_and_domain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drop_schema_if_exists(schema_name: str) -> None:
    """
    Dropa o schema do tenant diretamente no PostgreSQL, caso exista.

    Isso é necessário porque, por padrão, o django-tenants NÃO derruba o schema
    quando o tenant é deletado (a não ser que TENANT_AUTO_DROP_SCHEMA=True).
    """
    # Sempre trabalhar a partir do schema público ao manipular schemas.
    connection.set_schema_to_public()

    with connection.cursor() as cursor:
        # OBS: usamos f-string porque é teste e schema_name é controlado (numérico).
        # Em código de produção, seria melhor usar psycopg2.sql para compor identificadores.
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')
        logger.warning('Schema de teste droppado (se existia): %s', schema_name)


def _cleanup_tenant_if_exists(schema_name: str) -> None:
    """
    Remove um tenant de testes (e seu domínio) e garante que o schema
    físico correspondente seja derrubado.

    Isso evita que execuções anteriores de testes deixem lixo no banco
    e causem falhas por UNIQUE CONSTRAINT (por exemplo, em Filial.cnpj).
    """
    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    # Garantir que estamos no schema público antes de mexer em Tenant/Domain.
    connection.set_schema_to_public()

    tenant = TenantModel.objects.filter(schema_name=schema_name).first()
    if tenant:
        logger.warning("Removendo tenant de teste pré-existente: %s", schema_name)
        DomainModel.objects.filter(tenant=tenant).delete()
        tenant.delete()

    # Mesmo que não exista mais Tenant, o schema físico pode ter ficado.
    _drop_schema_if_exists(schema_name)


def _build_payload_tenant_1():
    """
    Payload base para o primeiro tenant de teste.

    CNPJs escolhidos para evitar colisão com seeds / outros testes.
    """
    return {
        # schema_name do tenant
        "cnpj_raiz": "99111111000191",
        "nome": "Minha Empresa LTDA",
        "domain": "tenant-99111111000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Minha Empresa LTDA",
            "nome_fantasia": "Loja Centro",
            # CNPJ da filial (único dentro do schema)
            "cnpj": "99111111000109",
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
                "numero": "1000",
                "complemento": "Conj 101",
                "referencia": "Próx. metrô",
                "cep": "01311000",
            },
        },
    }


def _build_payload_tenant_2_mesma_localizacao():
    """
    Mesmo endereço (mesma hierarquia de localização), mas CNPJ de filial diferente
    para respeitar a constraint de unicidade em Filial.cnpj.
    """
    return {
        "cnpj_raiz": "99222222000191",
        "nome": "Outra Empresa LTDA",
        "domain": "tenant-99222222000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Outra Empresa LTDA",
            "nome_fantasia": "Loja Bairro",
            # CNPJ propositalmente diferente do primeiro tenant
            "cnpj": "99222222000109",
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
                "numero": "2000",
                "complemento": "",
                "referencia": "",
                "cep": "01311000",
            },
        },
    }


# ---------------------------------------------------------------------------
# Fixture de isolamento (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_tenants_testes():
    """
    Executa antes e depois de CADA teste deste módulo, garantindo que os
    tenants de teste e seus schemas não existam antes de começar, nem
    permaneçam depois.

    Isso resolve interferência entre testes mesmo com django-tenants
    não derrubando schemas automaticamente.
    """
    for schema_name in ("99111111000191", "99222222000191"):
        _cleanup_tenant_if_exists(schema_name)
    yield
    for schema_name in ("99111111000191", "99222222000191"):
        _cleanup_tenant_if_exists(schema_name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token",
)
def test_criar_tenant_cria_schema_filial_e_endereco_completo():
    """
    Cria um tenant via endpoint público e garante que:

      - Tenant + Domain são criados no schema público.
      - No schema do tenant são criados:
        Pais, UF, Municipio, Bairro, Logradouro, Endereco, Filial.
    """
    _bootstrap_public_tenant_and_domain()

    payload = _build_payload_tenant_1()

    # Garante que estamos no schema público para criar novo Tenant.
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    logger.info("DEBUG: reverse('tenants:criar-tenant') = %s", url)
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token",
    }

    resp = client.post(url, data=payload, format="json", **headers)
    assert resp.status_code == 201, resp.content

    body = resp.json()
    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    tenant = TenantModel.objects.get(schema_name=payload["cnpj_raiz"])
    assert tenant.cnpj_raiz == payload["cnpj_raiz"]

    domain = DomainModel.objects.get(
        domain=payload["domain"],
        tenant=tenant,
        is_primary=True,
    )
    assert domain is not None

    with schema_context(tenant.schema_name):
        Pais = apps.get_model("enderecos", "Pais")
        UFModel = apps.get_model("enderecos", "UF")
        MunicipioModel = apps.get_model("enderecos", "Municipio")
        BairroModel = apps.get_model("enderecos", "Bairro")
        LogradouroModel = apps.get_model("enderecos", "Logradouro")
        EnderecoModel = apps.get_model("enderecos", "Endereco")
        FilialModel = apps.get_model("filial", "Filial")

        filial = FilialModel.objects.get(id=body["filial_id"])
        end_payload = payload["filial"]["endereco"]

        assert filial.cnpj == payload["filial"]["cnpj"]
        assert filial.razao_social == payload["filial"]["razao_social"]

        endereco = filial.endereco
        assert endereco.cep == end_payload["cep"]
        assert endereco.numero == end_payload["numero"]

        logradouro = endereco.logradouro
        assert logradouro.tipo == end_payload["logradouro_tipo"]
        assert logradouro.nome == end_payload["logradouro_nome"]

        bairro = logradouro.bairro
        assert bairro.nome == end_payload["bairro"]

        municipio = bairro.municipio
        assert municipio.codigo_ibge == end_payload["municipio"]["codigo_ibge"]

        uf = municipio.uf
        assert uf.sigla == end_payload["uf"]["sigla"]

        pais = uf.pais
        assert pais.codigo_nfe == end_payload["pais"]["codigo_nfe"]

        # Atalhos da filial (properties)
        assert filial.uf == uf.sigla
        assert filial.cMun == municipio.codigo_ibge
        assert filial.xMun == municipio.nome
        assert filial.cPais == pais.codigo_nfe
        assert filial.xPais == pais.nome


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token",
)
def test_criar_tenant_reutiliza_hierarquia_endereco_quando_mesmos_codigos():
    """
    Cria DOIS tenants com a mesma hierarquia de localização e garante que:

      - Em cada schema de tenant existe apenas 1 registro de
        Pais, UF, Municipio, Bairro, Logradouro.
      - Cada tenant tem sua própria Filial/Endereco
        (com CNPJs distintos, respeitando unique em Filial.cnpj).
    """
    _bootstrap_public_tenant_and_domain()

    payload1 = _build_payload_tenant_1()
    payload2 = _build_payload_tenant_2_mesma_localizacao()

    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token",
    }

    # 1º tenant
    resp1 = client.post(url, data=payload1, format="json", **headers)
    assert resp1.status_code == 201, resp1.content
    body1 = resp1.json()

    # 2º tenant (mesma localização, mas CNPJ / dados distintos)
    resp2 = client.post(url, data=payload2, format="json", **headers)
    assert resp2.status_code == 201, resp2.content
    body2 = resp2.json()

    TenantModel = get_tenant_model()
    tenant1 = TenantModel.objects.get(schema_name=payload1["cnpj_raiz"])
    tenant2 = TenantModel.objects.get(schema_name=payload2["cnpj_raiz"])

    # -------------------------------
    # Schema do 1º tenant
    # -------------------------------
    with schema_context(tenant1.schema_name):
        Pais = apps.get_model("enderecos", "Pais")
        UFModel = apps.get_model("enderecos", "UF")
        MunicipioModel = apps.get_model("enderecos", "Municipio")
        BairroModel = apps.get_model("enderecos", "Bairro")
        LogradouroModel = apps.get_model("enderecos", "Logradouro")
        EnderecoModel = apps.get_model("enderecos", "Endereco")
        FilialModel = apps.get_model("filial", "Filial")

        assert Pais.objects.count() == 1
        assert UFModel.objects.count() == 1
        assert MunicipioModel.objects.count() == 1
        assert BairroModel.objects.count() == 1
        assert LogradouroModel.objects.count() == 1

        assert FilialModel.objects.count() == 1
        assert EnderecoModel.objects.count() == 1

        filial1 = FilialModel.objects.get(id=body1["filial_id"])
        assert filial1.cnpj == payload1["filial"]["cnpj"]

    # -------------------------------
    # Schema do 2º tenant
    # -------------------------------
    with schema_context(tenant2.schema_name):
        Pais = apps.get_model("enderecos", "Pais")
        UFModel = apps.get_model("enderecos", "UF")
        MunicipioModel = apps.get_model("enderecos", "Municipio")
        BairroModel = apps.get_model("enderecos", "Bairro")
        LogradouroModel = apps.get_model("enderecos", "Logradouro")
        EnderecoModel = apps.get_model("enderecos", "Endereco")
        FilialModel = apps.get_model("filial", "Filial")

        assert Pais.objects.count() == 1
        assert UFModel.objects.count() == 1
        assert MunicipioModel.objects.count() == 1
        assert BairroModel.objects.count() == 1
        assert LogradouroModel.objects.count() == 1

        assert FilialModel.objects.count() == 1
        assert EnderecoModel.objects.count() == 1

        filial2 = FilialModel.objects.get(id=body2["filial_id"])
        assert filial2.cnpj == payload2["filial"]["cnpj"]
