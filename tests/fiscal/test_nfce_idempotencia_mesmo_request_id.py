# fiscal/tests/test_nfce_idempotencia_mesmo_request_id.py
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
    """
    Garante:
      - Tenant PUBLIC
      - Tenant de teste (schema = TENANT_SCHEMA)
      - Domain(TENANT_HOST) -> TENANT_SCHEMA no PUBLIC
    """
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    # PUBLIC
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(cnpj_raiz="00000000000000", nome="PUBLIC", premium_db_alias=None),
    )

    # TENANT DE TESTE
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(cnpj_raiz=TENANT_SCHEMA, nome="Tenant Teste", premium_db_alias=None),
    )

    # DOMAIN → TENANT
    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults=dict(tenant=ten, is_primary=True),
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
    """
    Gera Access Token válido (SimpleJWT) para passar no header Authorization.
    """
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def _make_client_jwt(user):
    """
    Cria um APIClient pronto para o tenant por Host + Authorization Bearer + X-Tenant-ID.
    Um client NOVO por thread (thread-safe).
    """
    token = _jwt_for_user(user)
    client = APIClient()
    client.defaults["HTTP_HOST"] = TENANT_HOST
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}",
        **{"HTTP_X_TENANT_ID": TENANT_SCHEMA},
    )
    return client


def _post_reserva(client: APIClient, terminal_id, serie, request_id):
    payload = {
        "terminal_id": str(terminal_id),
        "serie": int(serie),
        "request_id": str(request_id),
    }
    # Atenção: o prefixo /api/v1/ já é provido pelos urls de tenant (config.urls)
    return client.post("/api/v1/fiscal/nfce/reservar-numero", data=payload, format="json")


@override_settings(
    # Força usar as URLs de tenant (evita cair em urls_public)
    ROOT_URLCONF="config.urls",
    # Cache local (se outro teste ativar throttle)
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "pdv-tests"}},
    # Garante que o host de teste é aceito mesmo com DEBUG=False
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_idempotencia_em_paralelo_mesmo_request_id(caplog):
    """
    Mesmo request_id em 8 requisições concorrentes:
    - Todas retornam 200
    - Todas retornam o MESMO número
    - Apenas 1 NfceNumeroReserva para o request_id
    - numero_atual do terminal avança apenas +1
    """
    _bootstrap_public_tenant_and_domain()

    User = get_user_model()

    # 1) Dados no schema do tenant
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

        # vínculo user↔filial (regra de permissão)
        user.userfilial_set.create(filial_id=filial.id)

        term.refresh_from_db()
        initial_num = term.numero_atual or 0

    # 2) Concorrência contra a VIEW com JWT real (middleware-friendly)
    req_id = uuid.uuid4()
    serie = 1
    caplog.clear()

    def worker():
        # Cada thread abre suas próprias conexões e as fecha no final
        close_old_connections()
        try:
            client = _make_client_jwt(user)
            resp = _post_reserva(client, term.id, serie, req_id)
            return resp
        finally:
            # Fecha conexões associadas a esta thread (evita leak no teardown)
            close_old_connections()

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(worker) for _ in range(8)]
        results = [f.result() for f in as_completed(futures)]

    # 3) Todos 200
    statuses = [r.status_code for r in results]
    assert all(s == 200 for s in statuses), f"Statuses recebidos: {statuses}"

    # 4) Payloads coerentes
    payloads = [r.json() for r in results]
    numeros = {p["numero"] for p in payloads}
    series = {p["serie"] for p in payloads}
    reqs = {p["request_id"] for p in payloads}
    assert len(numeros) == 1, f"Mais de um número retornado: {numeros}"
    assert series == {serie}, f"Séries divergentes: {series}"
    assert reqs == {str(req_id)}, f"Request_ids divergentes: {reqs}"

    # 5) 1 reserva e avanço +1
    with schema_context(TENANT_SCHEMA):
        reservas = NfceNumeroReserva.objects.filter(request_id=req_id).all()
        assert reservas.count() == 1, f"Esperava 1 reserva; obtive {reservas.count()}"
        term.refresh_from_db()
        assert term.numero_atual == initial_num + 1, (
            f"numero_atual esperado: {initial_num + 1}, obtido: {term.numero_atual}"
        )
