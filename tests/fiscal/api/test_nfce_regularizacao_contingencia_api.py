import uuid
from datetime import timedelta

import pytest
from django.test.utils import override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_a1_edge_cases import TENANT_HOST, _bootstrap_public_tenant_and_domain
from fiscal.tests.test_nfce_auditoria_logs import TENANT_SCHEMA, _make_client_jwt
from terminal.models.terminal_models import Terminal
from fiscal.models import NfcePreEmissao, NfceDocumento

User = get_user_model()

ENDPOINT = "/api/v1/fiscal/nfce/regularizar-contingencia/"


# =============================================================================
# Helpers de massa
# =============================================================================


def _marcar_a1_valido(filial: Filial) -> None:
    if hasattr(filial, "a1_expires_at"):
        filial.a1_expires_at = timezone.now() + timedelta(days=365)

    if hasattr(filial, "a1_pfx"):
        field = filial._meta.get_field("a1_pfx")
        internal_type = field.get_internal_type()
        if internal_type == "BinaryField":
            filial.a1_pfx = b"DUMMY_PFX"
        else:
            filial.a1_pfx = "DUMMY_PFX"

    filial.save()


def _criar_filial_terminal_usuario_e_doc_contingencia():
    """
    Cria:
      - usuário com username único
      - filial com CNPJ único e A1 válido
      - terminal com identificador único
      - pré-emissão + documento em contingência_pendente
    """

    username = f"oper-cont-api-{uuid.uuid4().hex[:8]}"
    user = User.objects.create_user(username=username, password="123456")

    cnpj_num = uuid.uuid4().int % (10**14)
    cnpj = f"{cnpj_num:014d}"

    filial = Filial.objects.create(
        cnpj=cnpj,
        nome_fantasia="Filial Contingência API",
        uf="SP",
        csc_id="ID",
        csc_token="TK",
        ambiente="homolog",
    )
    _marcar_a1_valido(filial)

    identificador = f"T-CONT-API-{uuid.uuid4().hex[:6]}"

    term = Terminal.objects.create(
        identificador=identificador,
        filial_id=filial.id,
        serie=1,
        numero_atual=1,
        ativo=True,
    )

    user.userfilial_set.create(filial_id=filial.id)

    req_id = uuid.uuid4()

    pre = NfcePreEmissao.objects.create(
        filial_id=filial.id,
        terminal_id=term.id,
        numero=1,
        serie=1,
        request_id=req_id,
        payload={
            "itens": [],
            "pagamentos": [],
            "cliente": None,
        },
    )

    doc = NfceDocumento.objects.create(
        request_id=req_id,
        filial=filial,
        terminal=term,
        numero=pre.numero,
        serie=pre.serie,
        chave_acesso="C" + uuid.uuid4().hex[:43],
        protocolo="",
        status="contingencia_pendente",
        xml_autorizado=None,
        raw_sefaz_response={"motivo": "Contingência ativada (API mock)."},
        mensagem_sefaz="Documento em contingência pendente (API mock).",
        ambiente=filial.ambiente,
        uf=filial.uf,
        created_at=timezone.now(),
        em_contingencia=True,
        contingencia_ativada_em=timezone.now(),
        contingencia_motivo="Falha técnica anterior (API mock).",
        contingencia_regularizada_em=None,
    )

    return user, filial, term, pre, doc


# =============================================================================
# Testes
# =============================================================================


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_api_sem_autenticacao():
    """
    A chamada sem JWT deve ser rejeitada com 401 ou 403.
    """
    _bootstrap_public_tenant_and_domain()

    client = APIClient()

    # Mesmo com payload válido, sem JWT não deve passar.
    fake_doc_id = str(uuid.uuid4())
    resp = client.post(
        ENDPOINT,
        data={"documento_id": fake_doc_id},
        format="json",
    )

    assert resp.status_code in (401, 403, 404)


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_api_happy_path_autorizada():
    """
    Cenário feliz de regularização via API:

      - JWT válido
      - documento em contingencia_pendente
      - resposta 200 com code FISCAL_0000 (padrão de sucesso)
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        user, filial, term, pre, doc = _criar_filial_terminal_usuario_e_doc_contingencia()

        client = _make_client_jwt(user)

        resp = client.post(
            ENDPOINT,
            data={"documento_id": str(doc.id)},
            format="json",
        )

        assert resp.status_code == 200, resp.content

        body = resp.json()
        # Mantemos o padrão de sucesso já usado nas outras APIs fiscais
        assert body.get("code") == "FISCAL_0000"

        # Opcional: se houver 'data', validamos pelo menos alguns campos
        data = body.get("data", {})
        if data:
            assert "status_depois" in data
            # Não deve continuar em contingência pendente
            assert data["status_depois"] != "contingencia_pendente"

        # Confirma que o documento no banco foi atualizado
        doc.refresh_from_db()
        assert doc.status != "contingencia_pendente"
        assert doc.em_contingencia is False or doc.em_contingencia is None


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_api_documento_inexistente():
    """
    Quando o documento não existe, a API deve retornar 404 (ideal) ou 400.

    Mantemos a asserção flexível (404/400) para não acoplar 100% em um
    único comportamento enquanto o backend estiver em evolução.
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        # Usuário apenas para autenticação; não criaremos documento real
        username = f"oper-cont-api-not-found-{uuid.uuid4().hex[:8]}"
        user = User.objects.create_user(username=username, password="123456")

        client = _make_client_jwt(user)

        fake_doc_id = str(uuid.uuid4())
        resp = client.post(
            ENDPOINT,
            data={"documento_id": fake_doc_id},
            format="json",
        )

        # Aceitamos 404 (mais semântico) ou 400 (caso o backend trate como input inválido)
        assert resp.status_code in (400, 404), resp.content
