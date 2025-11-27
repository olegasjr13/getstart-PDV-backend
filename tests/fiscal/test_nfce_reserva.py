# -*- coding: utf-8 -*-
"""
Fluxos principais de reserva:
- A1 expirado -> 403 (FISCAL_3001) e numero_atual não avança
- Sucesso + idempotência -> 200 e mesmo número ao repetir request_id
- Série divergente -> 400/422 (FISCAL_3002)
- Terminal inexistente -> 404 (TERMINAL_2001)
"""

import uuid
import pytest
from django.test.utils import override_settings
from django_tenants.utils import schema_context, get_tenant_model
from django.apps import apps
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"
API_URL = "/api/v1/fiscal/nfce/reservar-numero"


def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")
    tenant, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults={"cnpj_raiz": TENANT_SCHEMA, "nome": "Cliente Demo"},
    )
    tenant.save()
    Domain.objects.get_or_create(
        domain=TENANT_HOST, defaults={"tenant": tenant, "is_primary": True}
    )


def _ensure_a1_valid(filial: Filial):
    filial.a1_expires_at = timezone.now() + timedelta(days=30)
    filial.save(update_fields=["a1_expires_at"])


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_bloqueio_a1_expirado():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Teste",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
            a1_expires_at=timezone.now() - timedelta(days=1),  # expirado
        )
        term = Terminal.objects.create(
            identificador="TERM-01",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = APIClient()
    c.force_authenticate(user=user)

    resp = c.post(
        API_URL,
        {"terminal_id": str(term.id), "serie": term.serie, "request_id": str(uuid.uuid4())},
        format="json",
        HTTP_HOST=TENANT_HOST,
    )
    assert resp.status_code == 403, resp.content
    assert resp.data.get("code") == "FISCAL_3001"

    with schema_context(TENANT_SCHEMA):
        term.refresh_from_db()
        assert (term.numero_atual or 0) == 0


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_reserva_sucesso_e_idempotencia():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Teste",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        term = Terminal.objects.create(
            identificador="TERM-01",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = APIClient()
    c.force_authenticate(user=user)

    req_id = str(uuid.uuid4())

    r1 = c.post(
        API_URL,
        {"terminal_id": str(term.id), "serie": term.serie, "request_id": req_id},
        format="json",
        HTTP_HOST=TENANT_HOST,
    )
    assert r1.status_code == 200, r1.content
    n1 = r1.data["numero"]

    r2 = c.post(
        API_URL,
        {"terminal_id": str(term.id), "serie": term.serie, "request_id": req_id},
        format="json",
        HTTP_HOST=TENANT_HOST,
    )
    assert r2.status_code == 200, r2.content
    assert r2.data["numero"] == n1

    # garante que numero_atual avançou apenas 1
    with schema_context(TENANT_SCHEMA):
        term.refresh_from_db()
        assert (term.numero_atual or 0) == 1


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_serie_divergente():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Teste",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        term = Terminal.objects.create(
            identificador="TERM-01",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = APIClient()
    c.force_authenticate(user=user)

    resp = c.post(
        API_URL,
        {"terminal_id": str(term.id), "serie": 999, "request_id": str(uuid.uuid4())},
        format="json",
        HTTP_HOST=TENANT_HOST,
    )
    assert resp.status_code in (400, 422), resp.content
    assert resp.data.get("code") == "FISCAL_3002"


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_terminal_inexistente():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Teste",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        user.userfilial_set.create(filial_id=filial.id)

    c = APIClient()
    c.force_authenticate(user=user)

    resp = c.post(
        API_URL,
        {"terminal_id": "00000000-0000-0000-0000-000000000000", "serie": 1, "request_id": str(uuid.uuid4())},
        format="json",
        HTTP_HOST=TENANT_HOST,
    )
    assert resp.status_code == 404, resp.content
    assert resp.data.get("code") == "TERMINAL_2001"
