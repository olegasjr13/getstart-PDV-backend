# tenants/tests/test_tenant_user_isolation.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework.test import APIClient

from commons.tests.helpers import _bootstrap_public_tenant_and_domain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de limpeza (para não interferir com outros testes)
# ---------------------------------------------------------------------------


def _drop_schema_if_exists(schema_name: str) -> None:
    """
    Dropa o schema diretamente no PostgreSQL, caso exista.
    Usado apenas em contexto de teste.
    """
    connection.set_schema_to_public()
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')
    logger.info("Schema de teste '%s' dropado (se existia).", schema_name)


def _cleanup_tenant_if_exists(schema_name: str) -> None:
    """
    Remove tenant + domains + schema físico, caso já existam.
    Garante que cada execução do teste comece limpa.
    """
    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    connection.set_schema_to_public()

    tenant = TenantModel.objects.filter(schema_name=schema_name).first()
    if tenant:
        logger.warning(
            "Removendo tenant de teste pré-existente: %s", schema_name
        )
        DomainModel.objects.filter(tenant=tenant).delete()
        tenant.delete()

    _drop_schema_if_exists(schema_name)


def _build_payload_tenant_1():
    """
    Payload do tenant 1.
    CNPJs específicos deste arquivo para evitar colisão.
    """
    return {
        "cnpj_raiz": "99666666000191",
        "nome": "Empresa Tenant 1 LTDA",
        "domain": "tenant-99666666000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Empresa Tenant 1 LTDA",
            "nome_fantasia": "Loja Tenant 1",
            "cnpj": "99666666000109",
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


def _build_payload_tenant_2():
    """
    Payload do tenant 2.
    CNPJs diferentes, mas mesmo padrão de endereço.
    """
    return {
        "cnpj_raiz": "99777777000191",
        "nome": "Empresa Tenant 2 LTDA",
        "domain": "tenant-99777777000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Empresa Tenant 2 LTDA",
            "nome_fantasia": "Loja Tenant 2",
            "cnpj": "99777777000109",
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
                "numero": "20",
                "complemento": "",
                "referencia": "",
                "cep": "01311000",
            },
        },
    }


@pytest.fixture(autouse=True)
def _cleanup_tenants_isolation():
    """
    Garante ambiente limpo antes e depois dos testes deste arquivo.
    """
    for schema_name in ("99666666000191", "99777777000191"):
        _cleanup_tenant_if_exists(schema_name)
    yield
    for schema_name in ("99666666000191", "99777777000191"):
        _cleanup_tenant_if_exists(schema_name)


# ---------------------------------------------------------------------------
# Teste principal de isolamento de usuários entre tenants
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-isolation",
)
def test_usuarios_admin_isolados_por_tenant():
    """
    Cenário:

    - Cria dois tenants via endpoint público (tenant 1 e tenant 2).
    - Cada criação gera uma Filial e um usuário ADMIN (via criar_tenant).

    Verifica:

    1) Usuário do tenant 1 acessa tenant 1 => OK
       Usuário do tenant 2 acessa tenant 2 => OK

    2) Usuário do tenant 1 tentando "acessar" tenant 2 => NÃO existe nesse tenant.
       Usuário do tenant 2 tentando "acessar" tenant 1 => NÃO existe nesse tenant.
    """
    logger.info("Iniciando cenário de isolamento de usuários entre dois tenants.")
    _bootstrap_public_tenant_and_domain()
    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token-isolation",
    }

    # ---------------------------
    # Cria tenant 1
    # ---------------------------
    payload1 = _build_payload_tenant_1()
    logger.info("Criando tenant 1 com CNPJ raiz=%s", payload1["cnpj_raiz"])
    resp1 = client.post(url, data=payload1, format="json", **headers)
    assert resp1.status_code == 201, resp1.content
    body1 = resp1.json()

    schema1 = body1["schema"]
    admin_username_1 = body1["admin_username"]
    logger.info(
        "Tenant 1 criado com schema=%s, admin_username=%s",
        schema1,
        admin_username_1,
    )

    # ---------------------------
    # Cria tenant 2
    # ---------------------------
    payload2 = _build_payload_tenant_2()
    logger.info("Criando tenant 2 com CNPJ raiz=%s", payload2["cnpj_raiz"])
    resp2 = client.post(url, data=payload2, format="json", **headers)
    assert resp2.status_code == 201, resp2.content
    body2 = resp2.json()

    schema2 = body2["schema"]
    admin_username_2 = body2["admin_username"]
    logger.info(
        "Tenant 2 criado com schema=%s, admin_username=%s",
        schema2,
        admin_username_2,
    )

    assert schema1 != schema2, "Schemas dos tenants devem ser diferentes."
    assert (
        admin_username_1 != admin_username_2
    ), "Usernames ADMIN dos tenants devem ser diferentes."

    # ---------------------------
    # Dentro do schema do tenant 1
    # ---------------------------
    with schema_context(schema1):
        User = get_user_model()
        user_app_label = User._meta.app_label
        UserFilial = apps.get_model(user_app_label, "UserFilial")
        FilialModel = apps.get_model("filial", "Filial")

        # ✅ Usuário tenant 1 acessa tenant 1 -> existe
        logger.info(
            "Iniciando: usuário ADMIN do tenant 1 acessando tenant 1 (schema=%s).",
            schema1,
        )
        user_t1 = User.objects.get(username=admin_username_1)
        assert user_t1.perfil == "ADMIN", (
            "Usuário ADMIN do tenant 1 deveria ter perfil 'ADMIN'. "
            f"perfil atual: {user_t1.perfil}"
        )
        assert user_t1.is_superuser is True, (
            "Usuário ADMIN do tenant 1 deveria ser superusuário."
        )

        assert FilialModel.objects.count() == 1, (
            "Tenant 1 deveria ter exatamente 1 filial criada."
        )
        filial_t1 = FilialModel.objects.first()
        assert UserFilial.objects.filter(
            user=user_t1, filial_id=filial_t1.id
        ).exists(), (
            "Usuário ADMIN do tenant 1 deve estar vinculado à sua filial no UserFilial."
        )
        logger.info(
            "Fim: usuário ADMIN do tenant 1 acessando tenant 1 -> resposta: PERMITIDO "
            "(usuário existe e está vinculado à filial)."
        )

        # 🚫 Usuário tenant 2 tentando 'acessar' tenant 1 -> NÃO deve existir aqui
        logger.info(
            "Iniciando: usuário ADMIN do tenant 2 tentando acessar tenant 1 (schema=%s).",
            schema1,
        )
        existe_user2_no_tenant1 = User.objects.filter(
            username=admin_username_2
        ).exists()
        assert not existe_user2_no_tenant1, (
            "Usuário ADMIN do tenant 2 NÃO deveria existir no schema do tenant 1 "
            "(isolamento de tenants violado)."
        )
        logger.info(
            "Fim: usuário ADMIN do tenant 2 tentando acessar tenant 1 -> resposta: "
            "NÃO PERMITIDO (usuário não existe neste tenant)."
        )

    # ---------------------------
    # Dentro do schema do tenant 2
    # ---------------------------
    with schema_context(schema2):
        User = get_user_model()
        user_app_label = User._meta.app_label
        UserFilial = apps.get_model(user_app_label, "UserFilial")
        FilialModel = apps.get_model("filial", "Filial")

        # ✅ Usuário tenant 2 acessa tenant 2 -> existe
        logger.info(
            "Iniciando: usuário ADMIN do tenant 2 acessando tenant 2 (schema=%s).",
            schema2,
        )
        user_t2 = User.objects.get(username=admin_username_2)
        assert user_t2.perfil == "ADMIN", (
            "Usuário ADMIN do tenant 2 deveria ter perfil 'ADMIN'. "
            f"perfil atual: {user_t2.perfil}"
        )
        assert user_t2.is_superuser is True, (
            "Usuário ADMIN do tenant 2 deveria ser superusuário."
        )

        assert FilialModel.objects.count() == 1, (
            "Tenant 2 deveria ter exatamente 1 filial criada."
        )
        filial_t2 = FilialModel.objects.first()
        assert UserFilial.objects.filter(
            user=user_t2, filial_id=filial_t2.id
        ).exists(), (
            "Usuário ADMIN do tenant 2 deve estar vinculado à sua filial no UserFilial."
        )
        logger.info(
            "Fim: usuário ADMIN do tenant 2 acessando tenant 2 -> resposta: PERMITIDO "
            "(usuário existe e está vinculado à filial)."
        )

        # 🚫 Usuário tenant 1 tentando 'acessar' tenant 2 -> NÃO deve existir aqui
        logger.info(
            "Iniciando: usuário ADMIN do tenant 1 tentando acessar tenant 2 (schema=%s).",
            schema2,
        )
        existe_user1_no_tenant2 = User.objects.filter(
            username=admin_username_1
        ).exists()
        assert not existe_user1_no_tenant2, (
            "Usuário ADMIN do tenant 1 NÃO deveria existir no schema do tenant 2 "
            "(isolamento de tenants violado)."
        )
        logger.info(
            "Fim: usuário ADMIN do tenant 1 tentando acessar tenant 2 -> resposta: "
            "NÃO PERMITIDO (usuário não existe neste tenant)."
        )

    logger.info("Cenário de isolamento de usuários entre tenants finalizado com sucesso.")
