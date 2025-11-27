# fiscal/tests/test_nfce_input_validation.py
import uuid
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context, get_tenant_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from django.utils import timezone
from datetime import timedelta

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"

def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(cnpj_raiz="00000000000000", nome="PUBLIC", premium_db_alias=None),
    )
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(cnpj_raiz=TENANT_SCHEMA, nome="Tenant Teste", premium_db_alias=None),
    )
    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST, defaults=dict(tenant=ten, is_primary=True)
    )
    if not created_dom and dom.tenant_id != ten.id:
        dom.tenant = ten
        dom.is_primary = True
        dom.save(update_fields=["tenant", "is_primary"])

def _jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)

def _make_client_jwt(user):
    client = APIClient()
    client.defaults["HTTP_HOST"] = TENANT_HOST
    if user:
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {_jwt_for_user(user)}",
            **{"HTTP_X_TENANT_ID": TENANT_SCHEMA},
        )
    else:
        client.defaults["HTTP_X_TENANT_ID"] = TENANT_SCHEMA
    return client

def _post_reserva_raw(client: APIClient, payload: dict):
    return client.post(
        "/api/v1/fiscal/nfce/reservar-numero",
        data=payload,
        format="json",
    )

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_terminal_id_malformatado_gera_400():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
    c = _make_client_jwt(user)

    resp = _post_reserva_raw(
        c,
        payload={"terminal_id": "NAO-UUID", "serie": 1, "request_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 400
    assert "terminal_id" in resp.json()

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_request_id_malformatado_gera_400():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
        filial = Filial.objects.create(
            cnpj="33333333000133", nome_fantasia="Filial", uf="SP",
            csc_id="ID", csc_token="TK", ambiente="homolog",
            a1_expires_at=timezone.now() + timedelta(days=1),
        )
        term = Terminal.objects.create(
            identificador="T1", serie=1, numero_atual=0, filial_id=filial.id
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = _make_client_jwt(user)
    resp = _post_reserva_raw(
        c,
        payload={"terminal_id": str(term.id), "serie": 1, "request_id": "NAO-UUID"},
    )
    assert resp.status_code == 400
    assert "request_id" in resp.json()

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_serie_invalida_gera_400():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
    c = _make_client_jwt(user)

    for invalid in [None, 0, -1, "abc"]:
        resp = _post_reserva_raw(
            c,
            payload={"terminal_id": str(uuid.uuid4()), "serie": invalid, "request_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 400
        assert "serie" in resp.json()
