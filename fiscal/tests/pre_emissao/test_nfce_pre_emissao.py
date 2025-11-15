# fiscal/tests/pre_emissao/test_nfce_pre_emissao.py

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

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"


# ---------------------------------------------------------------------
# Helpers padrão (mesmo estilo dos outros testes que já funcionam)
# ---------------------------------------------------------------------
def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    # PUBLIC
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(
            cnpj_raiz="00000000000000",
            nome="PUBLIC",
            premium_db_alias=None,
        ),
    )

    # Tenant de teste
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(
            cnpj_raiz=TENANT_SCHEMA,
            nome="Tenant Teste",
            premium_db_alias=None,
        ),
    )

    # Domain do tenant
    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults=dict(tenant=ten, is_primary=True),
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


def _post_pre_emissao(client: APIClient, request_id, payload: dict):
    """
    POST /api/v1/fiscal/nfce/pre-emissao com o mesmo padrão dos outros testes.
    """
    data = {"request_id": str(request_id)}
    data.update(payload)
    return client.post(
        "/api/v1/fiscal/nfce/pre-emissao",
        data=data,
        format="json",
    )


def _ensure_a1_valid(filial):
    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])


# ---------------------------------------------------------------------
# HAPPY PATH
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_happy_path():
    """
    Cenário feliz da pré-emissão:

    - Reserva de número já existente (NfceNumeroReserva).
    - Usuário vinculado à filial do terminal.
    - Certificado A1 válido.
    - POST /nfce/pre-emissao com o mesmo request_id da reserva deve:
        * retornar 201
        * retornar dados coerentes com a reserva
        * persistir um registro de NfcePreEmissao
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    NfceNumeroReserva = apps.get_model("fiscal", "NfceNumeroReserva")
    NfcePreEmissao = apps.get_model("fiscal", "NfcePreEmissao")

    # 1) Cria dados dentro do schema do tenant
    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre", password="123456")

        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Pré-Emissão",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="TERM-PRE",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        # vínculo user↔filial (regra usada na view)
        user.userfilial_set.create(filial_id=filial.id)

        # Reserva pré-existente (idempotência / vínculo do número)
        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            numero=1,
            serie=1,
            request_id=uuid.uuid4(),
        )

    # 2) Client autenticado com JWT, apontando para o tenant
    client = _make_client_jwt(user)

    # 3) Chama o endpoint de pré-emissão usando o request_id da reserva
    payload = {
        "itens": [],
        "total": 10,
        "observacao": "Pré-emissão de teste",
    }
    resp = _post_pre_emissao(client, reserva.request_id, payload)

    assert resp.status_code == 201, resp.content

    body = resp.json()

    # 4) Valida retorno coerente com a reserva
    assert body["numero"] == 1
    assert body["serie"] == 1
    assert body["terminal_id"] == str(term.id)
    assert body["filial_id"] == str(filial.id)
    assert body["request_id"] == str(reserva.request_id)
    assert body["payload"] == payload

    # 5) Valida que NfcePreEmissao foi persistida de forma idempotente
    with schema_context(TENANT_SCHEMA):
        pre_list = NfcePreEmissao.objects.filter(request_id=reserva.request_id)
        assert pre_list.count() == 1
        pre = pre_list.first()
        assert pre.numero == 1
        assert pre.serie == 1
        assert pre.filial_id == filial.id
        assert pre.terminal_id == term.id
        assert pre.payload == payload


# ---------------------------------------------------------------------
# REQUEST_ID obrigatório e malformado
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_request_id_obrigatorio():
    """
    Sem request_id → 400 + erro de validação.
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre2", password="123456")
        filial = Filial.objects.create(
            cnpj="22222222000122",
            nome_fantasia="Filial X",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        user.userfilial_set.create(filial_id=filial.id)

    client = _make_client_jwt(user)
    resp = client.post(
        "/api/v1/fiscal/nfce/pre-emissao",
        data={
            # sem request_id
            "total": 10,
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "request_id" in resp.json()


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_request_id_malformado():
    """
    request_id malformado → 400 + erro de validação.
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre3", password="123456")
        filial = Filial.objects.create(
            cnpj="33333333000133",
            nome_fantasia="Filial Y",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        user.userfilial_set.create(filial_id=filial.id)

    client = _make_client_jwt(user)
    resp = client.post(
        "/api/v1/fiscal/nfce/pre-emissao",
        data={
            "request_id": "NAO-UUID",
            "total": 10,
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "request_id" in resp.json()


# ---------------------------------------------------------------------
# Reserva inexistente
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_reserva_inexistente():
    """
    request_id sem NfceNumeroReserva associada → 404 com code FISCAL_4001.
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre4", password="123456")
        filial = Filial.objects.create(
            cnpj="44444444000144",
            nome_fantasia="Filial Z",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)
        user.userfilial_set.create(filial_id=filial.id)

    client = _make_client_jwt(user)
    req_id = uuid.uuid4()
    resp = _post_pre_emissao(
        client,
        req_id,
        {"total": 10},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "FISCAL_4001"


# ---------------------------------------------------------------------
# Usuário sem vínculo com a filial da reserva
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_usuario_sem_vinculo_filial():
    """
    Usuário sem vínculo com a filial da reserva → 403 AUTH_1006.
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    NfceNumeroReserva = apps.get_model("fiscal", "NfceNumeroReserva")

    with schema_context(TENANT_SCHEMA):
        # Usuário A
        user = User.objects.create_user(username="oper-pre5", password="123456")

        # Filial da reserva
        filial = Filial.objects.create(
            cnpj="55555555000155",
            nome_fantasia="Filial Reserva",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="TERM-PRE-SEM-VINC",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        # NÃO vincula o user à filial

        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            numero=5,
            serie=1,
            request_id=uuid.uuid4(),
        )

    client = _make_client_jwt(user)
    resp = _post_pre_emissao(
        client,
        reserva.request_id,
        {"total": 10},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("code") == "AUTH_1006"


# ---------------------------------------------------------------------
# Certificado A1 expirado
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_a1_expirado_retorna_403():
    """
    A1 expirado → 403 (regra de _assert_a1_valid).
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    NfceNumeroReserva = apps.get_model("fiscal", "NfceNumeroReserva")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre6", password="123456")

        filial = Filial.objects.create(
            cnpj="66666666000166",
            nome_fantasia="Filial A1 Expirado",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
            a1_expires_at=timezone.now() - timedelta(days=1),
        )

        term = Terminal.objects.create(
            identificador="TERM-PRE-A1-EXP",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        user.userfilial_set.create(filial_id=filial.id)

        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            numero=10,
            serie=1,
            request_id=uuid.uuid4(),
        )

    client = _make_client_jwt(user)
    resp = _post_pre_emissao(
        client,
        reserva.request_id,
        {"total": 10},
    )
    # de acordo com _assert_a1_valid, provavelmente 403
    assert resp.status_code == 403


# ---------------------------------------------------------------------
# Idempotência da pré-emissão
# ---------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_pre_emissao_idempotente_mesmo_request_id():
    """
    Duas chamadas com o mesmo request_id:

    - 1ª chamada → 201 + cria NfcePreEmissao.
    - 2ª chamada → 200 + reutiliza o mesmo registro (sem duplicar).
    """
    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    NfceNumeroReserva = apps.get_model("fiscal", "NfceNumeroReserva")
    NfcePreEmissao = apps.get_model("fiscal", "NfcePreEmissao")

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-pre7", password="123456")

        filial = Filial.objects.create(
            cnpj="77777777000177",
            nome_fantasia="Filial Idempotente",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="TERM-PRE-IDEMP",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        user.userfilial_set.create(filial_id=filial.id)

        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            numero=20,
            serie=1,
            request_id=uuid.uuid4(),
        )

    client = _make_client_jwt(user)
    payload = {"total": 99}

    # 1ª chamada → 201
    r1 = _post_pre_emissao(client, reserva.request_id, payload)
    assert r1.status_code == 201, r1.content

    # 2ª chamada → 200
    r2 = _post_pre_emissao(client, reserva.request_id, payload)
    assert r2.status_code == 200, r2.content

    with schema_context(TENANT_SCHEMA):
        all_pre = NfcePreEmissao.objects.filter(request_id=reserva.request_id)
        assert all_pre.count() == 1
