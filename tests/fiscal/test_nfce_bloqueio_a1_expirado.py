# fiscal/tests/test_nfce_bloqueio_a1_expirado.py
import uuid
from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from django_tenants.utils import schema_context, get_tenant_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal

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
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt_for_user(user)}",
        **{"HTTP_X_TENANT_ID": TENANT_SCHEMA},
    )
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
def test_bloqueio_a1_expirado():
    """
    Com A1 expirado, a pré-emissão deve ser BLOQUEADA (403 + code FISCAL_3001).
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111", nome_fantasia="Filial Teste", uf="SP",
            csc_id="ID", csc_token="TK", ambiente="homolog",
        )
        # força expiração
        filial.a1_expires_at = timezone.now() - timedelta(days=1)
        filial.save(update_fields=["a1_expires_at"])

        term = Terminal.objects.create(identificador="TERM-01", serie=1, numero_atual=0, filial_id=filial.id)
        user.userfilial_set.create(filial_id=filial.id)

    c = _make_client_jwt(user)
    r = _post_reserva(c, term.id, term.serie, uuid.uuid4())

    assert r.status_code == 403, r.content
    body = r.json()
    assert body.get("code") == ERR_A1_EXPIRED, body
