# fiscal/tests/test_nfce_sequencia_sem_buracos.py
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test.utils import override_settings
from django.utils import timezone
from django_tenants.utils import schema_context, get_tenant_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceNumeroReserva

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

def _ensure_a1_valid(filial: Filial):
    if not filial.a1_expires_at or filial.a1_expires_at <= timezone.now():
        filial.a1_expires_at = timezone.now() + timedelta(days=30)
        filial.save(update_fields=["a1_expires_at"])

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
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "pdv-tests"}},
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_sequencia_sem_buracos_em_paralelo_request_ids_distintos():
    """
    Vários request_id distintos em paralelo -> números devem formar sequência contínua
    (sem buracos) a partir do número atual (start+1 ... start+N).
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper1", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111", nome_fantasia="Filial Teste", uf="SP",
            csc_id="ID", csc_token="TK", ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        term = Terminal.objects.create(identificador="TERM-01", serie=1, numero_atual=0, filial_id=filial.id)
        user.userfilial_set.create(filial_id=filial.id)
        term.refresh_from_db()
        start = term.numero_atual or 0

    N = 12
    req_ids = [uuid.uuid4() for _ in range(N)]
    serie = 1

    def worker(rid):
        close_old_connections()
        try:
            c = _make_client_jwt(user)
            return _post_reserva(c, term.id, serie, rid)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=N) as ex:
        results = [f.result() for f in as_completed([ex.submit(worker, rid) for rid in req_ids])]

    statuses = [r.status_code for r in results]
    assert all(s == 200 for s in statuses), f"Statuses recebidos: {statuses}"

    nums = sorted({r.json()["numero"] for r in results})
    assert nums == list(range(start + 1, start + 1 + N)), f"Números não contínuos: {nums}"

    with schema_context(TENANT_SCHEMA):
        term.refresh_from_db()
        assert term.numero_atual == start + N
        # sanity: N reservas distintas
        assert NfceNumeroReserva.objects.count() == N
