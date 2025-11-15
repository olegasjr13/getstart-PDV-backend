# fiscal/tests/test_nfce_a1_edge_cases.py
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
ERR_A1_EXPIRED = "FISCAL_3001"

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

def _post_reserva(client: APIClient, terminal_id, serie, request_id):
    return client.post(
        "/api/v1/fiscal/nfce/reservar-numero",
        data={"terminal_id": str(terminal_id), "serie": int(serie), "request_id": str(request_id)},
        format="json",
    )

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_a1_expires_at_igual_agora_bloqueia():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
        filial = Filial.objects.create(
            cnpj="44444444000144", nome_fantasia="Filial", uf="SP",
            csc_id="ID", csc_token="TK", ambiente="homolog",
            a1_expires_at=timezone.now(),  # exatamente agora → bloqueia
        )
        term = Terminal.objects.create(
            identificador="T1", serie=1, numero_atual=0, filial_id=filial.id
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = _make_client_jwt(user)
    r = _post_reserva(c, term.id, 1, uuid.uuid4())
    assert r.status_code == 403, r.content
    assert r.json().get("code") == ERR_A1_EXPIRED

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_a1_expires_at_pouco_futuro_permite():
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
        filial = Filial.objects.create(
            cnpj="55555555000155", nome_fantasia="Filial", uf="SP",
            csc_id="ID", csc_token="TK", ambiente="homolog",
            a1_expires_at=timezone.now() + timedelta(seconds=1),
        )
        term = Terminal.objects.create(
            identificador="T1", serie=1, numero_atual=0, filial_id=filial.id
        )
        user.userfilial_set.create(filial_id=filial.id)

    c = _make_client_jwt(user)
    r = _post_reserva(c, term.id, 1, uuid.uuid4())
    assert r.status_code == 200, r.content
