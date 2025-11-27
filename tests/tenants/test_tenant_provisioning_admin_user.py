# tenants/tests/test_tenant_provisioning_admin_user.py

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
# Helpers de limpeza (para evitar interferência entre testes)
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


def _build_payload_tenant_admin():
    """
    Payload específico para este teste, com CNPJs únicos
    para evitar colisão com outros testes.
    """
    return {
        "cnpj_raiz": "99555555000191",
        "nome": "Empresa Admin Teste LTDA",
        "domain": "tenant-99555555000191.test.local",
        "premium_db_alias": None,
        "filial": {
            "razao_social": "Empresa Admin Teste LTDA",
            "nome_fantasia": "Loja Admin",
            "cnpj": "99555555000109",
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
                "numero": "300",
                "complemento": "",
                "referencia": "",
                "cep": "01311000",
            },
        },
    }


# ---------------------------------------------------------------------------
# Teste principal
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls_public",
    ALLOWED_HOSTS=["*", "testserver"],
    TENANT_PROVISIONING_TOKEN="test-token-admin",
)
def test_criar_tenant_cria_tenant_filial_e_usuario_admin():
    """
    Cenario completo de provisionamento:

    - Cria novo tenant via endpoint público.
    - Verifica no schema público:
        * Tenant criado com schema_name = cnpj_raiz
        * Domain principal criado.
    - Verifica no schema do tenant:
        * Filial inicial criada.
        * Usuário ADMIN criado (perfil=ADMIN, superuser, staff, ativo).
        * Vínculo UserFilial entre o ADMIN e a Filial.
    """
    payload = _build_payload_tenant_admin()
    schema_name = payload["cnpj_raiz"]
    domain_name = payload["domain"]

    # Garante ambiente limpo antes do teste
    _bootstrap_public_tenant_and_domain()
    _cleanup_tenant_if_exists(schema_name)

    connection.set_schema_to_public()

    client = APIClient()
    url = reverse("tenants:criar-tenant")
    headers = {
        "HTTP_X_TENANT_PROVISIONING_TOKEN": "test-token-admin",
    }

    resp = client.post(url, data=payload, format="json", **headers)
    assert resp.status_code == 201, resp.content

    body = resp.json()
    assert body["schema"] == schema_name
    assert body["domain"] == domain_name
    assert body["filial_id"] is not None
    assert body["admin_user_id"] is not None
    assert body["admin_username"] is not None

    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    # -------------------------------
    # Verificações no schema público
    # -------------------------------
    connection.set_schema_to_public()

    tenant = TenantModel.objects.get(schema_name=schema_name)
    assert tenant.cnpj_raiz == payload["cnpj_raiz"]

    domain = DomainModel.objects.get(
        domain=domain_name,
        tenant=tenant,
        is_primary=True,
    )
    assert domain is not None

    # -------------------------------
    # Verificações dentro do schema do tenant
    # -------------------------------
    with schema_context(schema_name):
        FilialModel = apps.get_model("filial", "Filial")
        User = get_user_model()
        user_app_label = User._meta.app_label
        UserFilial = apps.get_model(user_app_label, "UserFilial")

        # Filial
        assert FilialModel.objects.count() == 1
        filial = FilialModel.objects.get(id=body["filial_id"])
        assert filial.cnpj == payload["filial"]["cnpj"]
        assert filial.razao_social == payload["filial"]["razao_social"]

        # Usuário ADMIN
        admin_user = User.objects.get(id=body["admin_user_id"])
        assert admin_user.username == body["admin_username"]
        assert admin_user.perfil == "ADMIN"
        assert admin_user.is_superuser is True
        assert admin_user.is_staff is True
        assert admin_user.is_active is True

        # Vínculo UserFilial
        assert UserFilial.objects.filter(
            user=admin_user,
            filial_id=filial.id,
        ).exists()
