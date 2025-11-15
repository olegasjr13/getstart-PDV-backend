# -*- coding: utf-8 -*-
"""
Valida que a view exige autenticação (IsAuthenticated).
Sem Authorization -> 401 (ou 403, dependendo do setup).
"""

import pytest
from django.test.utils import override_settings
from django_tenants.utils import schema_context, get_tenant_model
from django.apps import apps
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from django.utils import timezone
from datetime import timedelta

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"
API_URL = "/api/v1/fiscal/nfce/reservar-numero"


def _bootstrap_public_tenant_and_domain():
    """Garante que o tenant e o domínio público existam para o middleware."""
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    tenant, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults={"cnpj_raiz": TENANT_SCHEMA, "nome": "Cliente Demo"},
    )
    # cria schema se ainda não existir (save em Tenant do django-tenants cria o schema)
    tenant.save()
    Domain.objects.get_or_create(
        domain=TENANT_HOST, defaults={"tenant": tenant, "is_primary": True}
    )


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_auth_obrigatorio_retorna_401_ou_403():
    _bootstrap_public_tenant_and_domain()

    # Criamos dados apenas para garantir que a rota está funcional
    User = get_user_model()
    with schema_context(TENANT_SCHEMA):
        User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Teste",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
            a1_expires_at=timezone.now() + timedelta(days=7),
        )
        Terminal.objects.create(
            identificador="TERM-01",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

    c = APIClient()
    # Sem autenticação de propósito
    resp = c.post(API_URL, {}, format="json", HTTP_HOST=TENANT_HOST)

    assert resp.status_code in (401, 403), resp.content
    # Quando 401, a mensagem costuma indicar ausência de credenciais
    if resp.status_code == 401:
        msg = str(resp.data.get("detail", "")).lower()
        assert "credenciais" in msg or "credentials" in msg or "autentica" in msg
