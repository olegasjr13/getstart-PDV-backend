# fiscal/tests/emissao/test_nfce_emissao_service.py

import uuid
from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceNumeroReserva
from fiscal.services.emissao_service import emitir_nfce, EmitirNfceResult

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"


# ---------------------------------------------------------------------------
# Helpers de tenant / auth (mesmo padrão dos outros testes fiscais)
# ---------------------------------------------------------------------------

def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    # schema public
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(
            cnpj_raiz="00000000000000",
            nome="PUBLIC",
            premium_db_alias=None,
        ),
    )

    # tenant do teste
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(
            cnpj_raiz=TENANT_SCHEMA,
            nome="Tenant Teste",
            premium_db_alias=None,
        ),
    )

    # domínio apontando para o tenant
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
    """
    APIClient com:
    - HTTP_HOST do tenant
    - Bearer JWT
    - X_TENANT_ID
    """
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


def _ensure_a1_valid(filial: Filial):
    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])


def _post_pre_emissao(client: APIClient, request_id, payload: dict):
    """
    Usa a view real de pré-emissão para criar NfcePreEmissao.
    Assim o teste não acopla a model diretamente.
    """
    body = {"request_id": str(request_id)}
    body.update(payload or {})
    return client.post(
        "/api/v1/fiscal/nfce/pre-emissao",
        data=body,
        format="json",
    )


# ---------------------------------------------------------------------------
# Fake SEFAZ client (implementa o contrato esperado pela service)
# ---------------------------------------------------------------------------

class FakeSefazClient:
    """
    Implementa o método emitir_nfce(pre_emissao=...) conforme o protocolo
    SefazClientProtocol definido em fiscal.services.emissao_service.
    """

    def emitir_nfce(self, *, pre_emissao):
        # pre_emissao é uma instância de NfcePreEmissao
        # Simulamos um retorno de autorização bem-sucedida.
        return {
            "chave_acesso": "NFe35181111111111111111550010000000011000000010",
            "protocolo": "135180000000001",
            "status": "autorizada",
            "xml_autorizado": "<xml>autorizado</xml>",
            "mensagem": "Autorizado o uso da NF-e",
            "raw": {
                "codigo": "100",
                "descricao": "Autorizado o uso da NF-e",
            },
        }


# ---------------------------------------------------------------------------
# Teste principal: fluxo feliz de emissão
# ---------------------------------------------------------------------------

@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_happy_path():
    """
    Fluxo feliz de emissão via service emitir_nfce:

    1. Cria user, filial, terminal e vínculo user↔filial.
    2. Cria reserva de número (NfceNumeroReserva).
    3. Chama a view de pré-emissão para gerar NfcePreEmissao.
    4. Chama a service emitir_nfce com FakeSefazClient.
    5. Valida o DTO EmitirNfceResult retornado.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        # usuário operacional
        user = User.objects.create_user(username="oper-emissao", password="123456")

        # filial com A1 válido
        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Emissão",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        # terminal
        term = Terminal.objects.create(
            identificador="TERM-EMISSAO",
            serie=1,
            numero_atual=0,
            filial_id=filial.id,
        )

        # vínculo user↔filial
        user.userfilial_set.create(filial_id=filial.id)

        # reserva pré-existente
        req_id = uuid.uuid4()
        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            numero=1,
            serie=1,
            request_id=req_id,
        )

    # client autenticado para chamar pré-emissão
    client = _make_client_jwt(user)

    payload = {
        "itens": [],
        "total": 10,
        "observacao": "Pré-emissão para teste de emissão",
    }

    # 1) cria pré-emissão REAL
    pre_resp = _post_pre_emissao(client, req_id, payload)
    assert pre_resp.status_code in (200, 201), pre_resp.content
    pre_body = pre_resp.json()
    assert pre_body["numero"] == reserva.numero
    assert pre_body["serie"] == reserva.serie

    # 2) emite NFC-e via service com fake SEFAZ
    fake_sefaz = FakeSefazClient()
    # ⚠️ Executa a service dentro do schema do tenant
    with schema_context(TENANT_SCHEMA):
        result = emitir_nfce(
            user=user,
            request_id=req_id,
            sefaz_client=fake_sefaz,
        )

    # 3) valida tipo e conteúdo do retorno
    assert isinstance(result, EmitirNfceResult)

    assert result.numero == reserva.numero
    assert result.serie == reserva.serie
    assert result.terminal_id == str(term.id)
    assert result.filial_id == str(filial.id)
    assert result.request_id == str(req_id)

    # campos da SEFAZ simulada
    assert result.chave_acesso == "NFe35181111111111111111550010000000011000000010"
    assert result.protocolo == "135180000000001"
    assert result.status == "autorizada"
    assert result.xml_autorizado == "<xml>autorizado</xml>"
    assert result.mensagem == "Autorizado o uso da NF-e"
    assert isinstance(result.raw_sefaz, dict)
    assert result.raw_sefaz.get("codigo") == "100"
