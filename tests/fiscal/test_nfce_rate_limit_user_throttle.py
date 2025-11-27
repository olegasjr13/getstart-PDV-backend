# fiscal/tests/test_nfce_rate_limit_user_throttle.py
import uuid

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import UserRateThrottle

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.views import nfce_views

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"


def _bootstrap_public_tenant_and_domain():
    """
    Garante que:
      - schema 'public' existe
      - schema TENANT_SCHEMA existe
      - Domain(TENANT_HOST) aponta para o tenant TENANT_SCHEMA
    """
    Tenant = apps.get_model("tenants", "Tenant")
    Domain = apps.get_model("tenants", "Domain")

    # PUBLIC
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults={
            "cnpj_raiz": "00000000000000",
            "nome": "PUBLIC",
            "premium_db_alias": None,
        },
    )

    # Tenant de teste
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults={
            "cnpj_raiz": TENANT_SCHEMA,
            "nome": "Tenant Teste",
            "premium_db_alias": None,
        },
    )

    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults={"tenant": ten, "is_primary": True},
    )
    if not created_dom and dom.tenant_id != ten.id:
        dom.tenant = ten
        dom.is_primary = True
        dom.save(update_fields=["tenant", "is_primary"])


def _ensure_a1_valid(filial: Filial):
    """
    Força o certificado A1 como válido (necessário para passar pela regra de bloqueio).
    """
    from django.utils import timezone
    from datetime import timedelta

    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])


def _jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def _make_client_jwt(user):
    """
    Cria APIClient com:
      - HTTP_HOST = TENANT_HOST (middleware resolve o tenant)
      - Authorization: Bearer <jwt>
      - X-Tenant-ID = TENANT_SCHEMA (backup, se você usar)
    """
    client = APIClient()
    client.defaults["HTTP_HOST"] = TENANT_HOST
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt_for_user(user)}",
        **{"HTTP_X_TENANT_ID": TENANT_SCHEMA},
    )
    return client


def _post_reserva(client: APIClient, terminal_id, serie, request_id):
    """
    Helper padronizado para chamar o endpoint de reserva de número.
    """
    return client.post(
        "/api/v1/fiscal/nfce/reservar-numero",
        data={
            "terminal_id": str(terminal_id),
            "serie": int(serie),
            "request_id": str(request_id),
        },
        format="json",
    )


class UserRateThrottleForTest(UserRateThrottle):
    """
    Throttle específica para o teste, desacoplada de REST_FRAMEWORK.DEFAULT_THROTTLE_RATES.
    """
    scope = "user"
    rate = "3/min"  # hard-coded para o teste


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "pdv-tests-throttle",
        }
    },
)
@pytest.mark.django_db(transaction=True)
def test_rate_limit_user_throttle_retorna_429_ao_exceder():
    """
    Cenário de rate-limit isolado e determinístico:

    - Usamos uma throttle específica (UserRateThrottleForTest) aplicada diretamente
      na APIView interna da view reservar_numero (reservar_numero.cls.throttle_classes).
    - Usamos cache locmem dedicado ("pdv-tests-throttle") para evitar interferência
      de outros testes.
    - Esperado:
        * 3 primeiras requisições => 200
        * 4ª requisição imediata   => 429 (throttled)
    """

    # 1) Prepara tenant + domain no PUBLIC (middleware depende disso)
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    # 2) Cria usuário, filial, terminal e vínculo no schema do tenant
    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-throttle", password="123456")
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Throttle",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="TERM-THROTTLE",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        # vínculo user↔filial (regra de permissão na service)
        user.userfilial_set.create(filial_id=filial.id)

    # 3) Monkeypatch da throttle da APIView interna (reservar_numero.cls)
    view_cls = getattr(nfce_views.reservar_numero, "cls", None)
    assert view_cls is not None, "View reservar_numero não possui atributo .cls (API view interna)."

    original_throttle_classes = getattr(view_cls, "throttle_classes", None)
    view_cls.throttle_classes = [UserRateThrottleForTest]

    try:
        def call():
            c = _make_client_jwt(user)
            return _post_reserva(c, term.id, term.serie, uuid.uuid4())

        # 3 chamadas dentro da janela → 200
        for i in range(3):
            r = call()
            assert r.status_code == 200, (
                f"Chamada {i+1} deveria ser 200, veio {r.status_code}: {r.content!r}"
            )

        # 4ª chamada imediatamente → 429 (throttled)
        r4 = call()
        assert (
            r4.status_code == 429
        ), f"Esperado 429; obtido {r4.status_code} content={r4.content!r}"

    finally:
        # 4) Restaura configuração original da view, garantindo que não afete outros testes
        if original_throttle_classes is not None:
            view_cls.throttle_classes = original_throttle_classes
        else:
            delattr(view_cls, "throttle_classes")
