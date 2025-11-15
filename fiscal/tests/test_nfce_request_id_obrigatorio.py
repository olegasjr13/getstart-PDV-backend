# fiscal/tests/test_nfce_request_id_obrigatorio.py
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context, get_tenant_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"

def _bootstrap_public_tenant_and_domain():
    """
    Garante:
    - schema 'public'
    - tenant do teste (TENANT_SCHEMA)
    - domain TENANT_HOST -> TENANT_SCHEMA
    """
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    # public
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(cnpj_raiz="00000000000000", nome="PUBLIC", premium_db_alias=None),
    )
    # tenant de teste
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(cnpj_raiz=TENANT_SCHEMA, nome="Tenant Teste", premium_db_alias=None),
    )
    # domain -> tenant
    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST, defaults=dict(tenant=ten, is_primary=True)
    )
    if not created_dom and dom.tenant_id != ten.id:
        dom.tenant = ten
        dom.is_primary = True
        dom.save(update_fields=["tenant", "is_primary"])

def _ensure_a1_valid(filial):
    from django.utils import timezone
    from datetime import timedelta
    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])

def _jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)

def _make_client_jwt(user):
    """
    APIClient com:
    - Host do tenant
    - Header X-Tenant-ID (middleware)
    - Authorization: Bearer <jwt> (IsAuthenticated)
    """
    c = APIClient()
    c.defaults["HTTP_HOST"] = TENANT_HOST
    c.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt_for_user(user)}",
        **{"HTTP_X_TENANT_ID": TENANT_SCHEMA},
    )
    return c

def _post_reserva_raw(client: APIClient, payload: dict):
    return client.post(
        "/api/v1/fiscal/nfce/reservar-numero",
        data=payload,
        format="json",  # garante JSON parser do DRF
    )

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_request_id_obrigatorio_retorna_400():
    """
    Faltando request_id (ou inválido) -> 400 com erro do serializer.
    """
    _bootstrap_public_tenant_and_domain()

    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
        filial = Filial.objects.create(
            cnpj="90123456000111",
            nome_fantasia="Filial X",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        term = Terminal.objects.create(
            identificador="TERM-X",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )
        # permissão: vínculo user↔filial
        user.userfilial_set.create(filial_id=filial.id)

    c = _make_client_jwt(user)

    # Sem request_id
    r1 = _post_reserva_raw(
        c,
        {"terminal_id": str(term.id), "serie": 1}
    )
    assert r1.status_code == 400, r1.content
    body1 = r1.json()
    assert "request_id" in body1, body1

    # request_id malformado
    r2 = _post_reserva_raw(
        c,
        {"terminal_id": str(term.id), "serie": 1, "request_id": "nao-uuid"}
    )
    assert r2.status_code == 400, r2.content
    body2 = r2.json()
    assert "request_id" in body2, body2
