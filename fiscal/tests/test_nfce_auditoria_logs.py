# fiscal/tests/test_nfce_auditoria_logs.py
import uuid
import logging
from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"


def _bootstrap_public_tenant_and_domain():
    """
    Garante que:
      - Tenant 'public' existe
      - Tenant TENANT_SCHEMA existe
      - Domain(TENANT_HOST) aponta para TENANT_SCHEMA
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

    # Tenant do teste
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults={
            "cnpj_raiz": TENANT_SCHEMA,
            "nome": "Tenant Teste",
            "premium_db_alias": None,
        },
    )

    # Domain → tenant de teste
    dom, created = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults={"tenant": ten, "is_primary": True},
    )
    if not created and dom.tenant_id != ten.id:
        dom.tenant = ten
        dom.is_primary = True
        dom.save(update_fields=["tenant", "is_primary"])


def _jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def _make_client_jwt(user):
    """
    Cria APIClient com JWT + headers de tenant corretos.
    """
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
        data={
            "terminal_id": str(terminal_id),
            "serie": int(serie),
            "request_id": str(request_id),
        },
        format="json",
    )


def _ensure_a1_valid(filial):
    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])


class _ListHandler(logging.Handler):
    """
    Handler simples em memória para capturar registros do logger 'pdv.fiscal'
    sem depender do pytest.caplog, que pode ser afetado pela configuração
    de LOGGING em JSON.
    """

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_auditoria_log_estruturado():
    """
    Garante que a view registra um log estruturado no logger 'pdv.fiscal' com:
      - message == 'nfce_reserva_numero'
      - campos principais no extra: tenant_id, user_id, filial_id, terminal_id,
        serie, numero, request_id, outcome='success'
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")

    # 1) Monta cenário no schema do tenant
    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper", password="x")
        filial = Filial.objects.create(
            cnpj="88888888000188",
            nome_fantasia="Filial",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T1",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )
        # vínculo user ↔ filial
        user.userfilial_set.create(filial_id=filial.id)

    client = _make_client_jwt(user)
    req_id = uuid.uuid4()

    # 2) Anexa handler em memória ao logger 'pdv.fiscal'
    logger = logging.getLogger("pdv.fiscal")
    mem_handler = _ListHandler()
    logger.addHandler(mem_handler)
    # garante que INFO será emitido
    old_level = logger.level
    logger.setLevel(logging.INFO)

    try:
        response = _post_reserva(client, term.id, 1, req_id)
        assert response.status_code == 200, response.content
    finally:
        # restaura estado do logger
        logger.setLevel(old_level)
        logger.removeHandler(mem_handler)

    # 3) Procura o log específico
    hit = next(
        (
            rec
            for rec in mem_handler.records
            if rec.getMessage() == "nfce_reserva_numero"
        ),
        None,
    )

    assert (
        hit is not None
    ), f"Esperado log 'nfce_reserva_numero' no logger 'pdv.fiscal'. Capturados: {[ (rec.name, rec.getMessage()) for rec in mem_handler.records ]}"

    # 4) Valida campos principais do extra
    extra = getattr(hit, "__dict__", {})

    # Os campos definidos na view fiscal/views/nfce_views.py
    # tenant_id, user_id, filial_id, terminal_id, serie, numero, request_id, outcome
    assert extra.get("event") == "nfce_reserva_numero"
    assert extra.get("tenant_id") == TENANT_SCHEMA
    assert extra.get("user_id") == user.id
    assert extra.get("filial_id") == str(filial.id)
    assert extra.get("terminal_id") == str(term.id)
    assert extra.get("serie") == 1
    # número reservado deve ser 1 no cenário inicial
    assert extra.get("numero") == 1
    assert extra.get("request_id") == str(req_id)
    assert extra.get("outcome") == "success"
