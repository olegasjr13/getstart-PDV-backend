# conftest.py (na raiz do projeto)

import logging

import pytest
from django.apps import apps
from django.db import connection
from django.urls import reverse
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework.test import APIClient

from commons.tests.helpers import _bootstrap_public_tenant_and_domain


logger = logging.getLogger(__name__)

TENANT1_SCHEMA = "99666666000191"
TENANT2_SCHEMA = "99777777000191"


# =============================================================================
# UTILITÁRIOS PARA LIMPEZA DE SCHEMA E TENANTS
# =============================================================================

def _drop_schema_if_exists(schema_name: str) -> None:
    """
    Dropa o schema diretamente no PostgreSQL, caso exista.
    Usado apenas para garantir um ambiente de testes 100% limpo.
    """
    connection.set_schema_to_public()
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')

    logger.info("[conftest] Schema '%s' dropado (se existia).", schema_name)


def _cleanup_tenant_if_exists(schema_name: str) -> None:
    """
    Remove tenant e domínio associados, além do schema físico.
    """
    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    connection.set_schema_to_public()

    tenant = TenantModel.objects.filter(schema_name=schema_name).first()
    if tenant:
        logger.warning("[conftest] Removendo tenant antigo: %s", schema_name)
        DomainModel.objects.filter(tenant=tenant).delete()
        tenant.delete()

    _drop_schema_if_exists(schema_name)


# =============================================================================
# HELPERS PARA CRIAÇÃO DE TENANTS
# =============================================================================

def _build_tenant_payload(
    cnpj_raiz: str,
    domain: str,
    empresa_nome: str,
    filial_cnpj: str,
    numero_logradouro: str,
) -> dict:
    """
    Monta payload usado para criar um tenant via API pública.
    """
    return {
        "cnpj_raiz": cnpj_raiz,
        "nome": empresa_nome,
        "domain": domain,
        "premium_db_alias": None,
        "filial": {
            "razao_social": empresa_nome,
            "nome_fantasia": f"Loja {empresa_nome}",
            "cnpj": filial_cnpj,
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
                "numero": numero_logradouro,
                "complemento": "",
                "referencia": "",
                "cep": "01311000",
            },
        },
    }


def _provision_tenant_via_api(payload: dict, token: str) -> dict:
    """
    Usa o endpoint /criar-tenant/ para criar o tenant real.
    """
    connection.set_schema_to_public()
    client = APIClient()

    url = reverse("tenants:criar-tenant")
    headers = {"HTTP_X_TENANT_PROVISIONING_TOKEN": token}

    logger.info("[conftest] Provisionando tenant %s...", payload["domain"])

    resp = client.post(url, data=payload, format="json", **headers)

    assert resp.status_code == 201, resp.content

    body = resp.json()

    logger.info(
        "[conftest] Tenant criado: schema=%s, admin=%s",
        body["schema"],
        body["admin_username"],
    )

    return body


# =============================================================================
# FIXTURE PRINCIPAL — DOIS TENANTS PRONTOS PARA USO EM QUALQUER TESTE
# =============================================================================

@pytest.fixture
def two_tenants_with_admins(db, settings):
    """
    Cria 2 tenants REAIS via /criar-tenant, com admins e filiais.
    
    Retorna:
    {
        "schema1": ...,
        "schema2": ...,
        "admin_username_1": ...,
        "admin_username_2": ...,
        "body1": {...},
        "body2": {...},
        "payload1": {...},
        "payload2": {...},
    }
    """

    # Configurações mínimas
    settings.ROOT_URLCONF = "config.urls_public"
    settings.ALLOWED_HOSTS = ["*", "testserver"]
    settings.TENANT_PROVISIONING_TOKEN = "test-token-global"

    # Remove lixo de execuções anteriores
    for schema in (TENANT1_SCHEMA, TENANT2_SCHEMA):
        _cleanup_tenant_if_exists(schema)

    # Boot do tenant público
    _bootstrap_public_tenant_and_domain()

    # Payloads
    payload1 = _build_tenant_payload(
        cnpj_raiz=TENANT1_SCHEMA,
        domain=f"tenant-{TENANT1_SCHEMA}.test.local",
        empresa_nome="Empresa Tenant 1 LTDA",
        filial_cnpj="99666666000109",
        numero_logradouro="10",
    )

    payload2 = _build_tenant_payload(
        cnpj_raiz=TENANT2_SCHEMA,
        domain=f"tenant-{TENANT2_SCHEMA}.test.local",
        empresa_nome="Empresa Tenant 2 LTDA",
        filial_cnpj="99777777000109",
        numero_logradouro="20",
    )

    # Cria os tenants
    body1 = _provision_tenant_via_api(payload1, settings.TENANT_PROVISIONING_TOKEN)
    body2 = _provision_tenant_via_api(payload2, settings.TENANT_PROVISIONING_TOKEN)

    ctx = {
        "schema1": body1["schema"],
        "schema2": body2["schema"],
        "admin_username_1": body1["admin_username"],
        "admin_username_2": body2["admin_username"],
        "body1": body1,
        "body2": body2,
        "payload1": payload1,
        "payload2": payload2,
    }

    yield ctx

    # Cleanup final
    for schema in (TENANT1_SCHEMA, TENANT2_SCHEMA):
        _cleanup_tenant_if_exists(schema)


# =============================================================================
# FIXTURES MELHORADAS — FACILITAM O USO EM TESTES MULTITENANT
# =============================================================================

@pytest.fixture
def admin_user():
    """
    Retorna uma função que, dado o username, retorna o objeto User real.
    """
    User = apps.get_model("usuario", "User")

    def _get(username: str):
        return User.objects.get(username=username)

    return _get


@pytest.fixture
def tenant_client(client):
    """
    Fixture para criar um client já autenticado e dentro de schema_context.

    Uso:
        client, ctx = tenant_client(schema, user)
        with ctx:
            resp = client.get(...)
    """
    def _build(schema: str, user):
        client.force_authenticate(user=user)
        return client, schema_context(schema)

    return _build


@pytest.fixture
def tenant_api(tenant_client):
    """
    Fixture simplificada para uso direto em testes.
    
    Uso:
        api = tenant_api(schema, admin)
        resp = api.get(url)
        resp = api.post(url, data={})
    """

    class TenantAPI:
        def __init__(self, schema: str, user):
            self.schema = schema
            self.user = user

        def _execute(self, method: str, url: str, **kwargs):
            client, ctx = tenant_client(self.schema, self.user)
            with ctx:
                return getattr(client, method)(url, **kwargs)

        # atalhos
        def get(self, url, **kw): return self._execute("get", url, **kw)
        def post(self, url, **kw): return self._execute("post", url, **kw)
        def put(self, url, **kw): return self._execute("put", url, **kw)
        def patch(self, url, **kw): return self._execute("patch", url, **kw)
        def delete(self, url, **kw): return self._execute("delete", url, **kw)

    def _factory(schema: str, user):
        return TenantAPI(schema, user)

    return _factory
