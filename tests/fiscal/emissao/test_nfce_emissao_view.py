import uuid

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from filial.models.filial_models import Filial
from fiscal.models import NfceDocumento, NfceNumeroReserva

# Reaproveita o fake de SEFAZ já usado nos testes de serviço
from fiscal.sefaz_clients import MockSefazClient
#from tests.fiscal.emissao.test_nfce_emissao_service import FakeSefazClient
from usuario.models.usuario_models import UserFilial



pytestmark = pytest.mark.django_db(transaction=True)

class FakeSefazClient(MockSefazClient):
    def emitir_nfce(self, *, pre_emissao):
        filial = Filial.objects.get(id=pre_emissao.filial_id)

        resp = self.autorizar_nfce(
            filial=filial,
            pre_emissao=pre_emissao,
            numero=pre_emissao.numero,
            serie=pre_emissao.serie,
        )

        status = "autorizada" if resp.codigo == 100 else "rejeitada"

        # Cria o documento no banco para o teste
        doc = NfceDocumento.objects.create(
            filial_id=pre_emissao.filial_id,
            terminal_id=getattr(pre_emissao, "terminal_id", None),
            numero=pre_emissao.numero,
            serie=pre_emissao.serie,
            request_id=pre_emissao.request_id,
            status=status,
            chave_acesso=resp.chave_acesso,
            protocolo=resp.protocolo,
            xml_autorizado=resp.xml_autorizado,
            mensagem=resp.mensagem,
        )

        return {
            "chave_acesso": resp.chave_acesso,
            "protocolo": resp.protocolo,
            "status": status,
            "xml_autorizado": resp.xml_autorizado,
            "mensagem": resp.mensagem,
            "raw": resp.raw,
        }


def _make_client_for_schema(schema_name: str, user) -> APIClient:
    """
    Cria um APIClient no padrão dos testes de integração:
    - HOST = tenant-<schema>.test.local
    - X_TENANT_ID = <schema>
    - JWT Bearer do usuário informado.
    """
    client = APIClient()
    host = f"tenant-{schema_name}.test.local"
    token = str(RefreshToken.for_user(user).access_token)

    client.defaults["HTTP_HOST"] = host
    client.defaults["HTTP_X_TENANT_ID"] = schema_name
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    return client


def _ensure_a1_valid(filial):
    from django.utils import timezone
    from datetime import timedelta
    A1 = apps.get_model("filial", "FilialCertificadoA1")

    cert, _ = A1.objects.get_or_create(
        filial=filial,
        defaults={
            "a1_pfx": b"fake",
            "senha_hash": "fake",
            "a1_expires_at": timezone.now() + timedelta(days=1),
        },
    )

    cert.a1_expires_at = timezone.now() + timedelta(days=10)
    cert.save(update_fields=["a1_expires_at"])

    print("DEBUG: a1_expires_at:", cert.a1_expires_at)

def _post_pre_emissao(client: APIClient, request_id, payload: dict):
    """
    Chama a view real de pré-emissão NFC-e.
    """
    print("DEBUG: Fazendo pré-emissão NFC-e via view para request_id:", request_id)
    body = {"request_id": str(request_id)}
    body.update(payload or {})
    print("DEBUG: Dados de pré-emissão:", body)
    return client.post(
        "/api/v1/fiscal/nfce/pre-emissao",
        data=body,
        format="json",
    )
    

# -------------------------------------------------------------------------
# 1) Happy path da view emitir_nfce_view
# -------------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", "testserver"],
)
def test_emitir_nfce_view_happy_path(two_tenants_with_admins, monkeypatch):
    schema1 = two_tenants_with_admins["schema1"]

    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")

    # ------------------------------------------------------------------
    # Cenário dentro do schema do tenant
    # ------------------------------------------------------------------
    with schema_context(schema1):
        # Usuário operador no schema do tenant
        user = User.objects.create_user(
            username="oper-view-ok",
            password="123456",
        )

        filial = Filial.objects.first()
        assert filial is not None, "Nenhuma Filial existente no tenant de teste."
        print("DEBUG: Filial existente:", filial)
        _ensure_a1_valid(filial)

        terminal = Terminal.objects.create(
            identificador="TERM-VIEW-01",
            filial=filial,
            ativo=True,
        )
        print("DEBUG: Terminal criado:", terminal)
        # Vínculo user ↔ filial, conforme modelo real
        UserFilial.objects.create(
            user=user,
            filial_id=filial.id,
        )
        print ("DEBUG: Vínculo UserFilial criado para usuário:", user)
        # Reserva de número pré-existente
        req_id = uuid.uuid4()
        NfceNumeroReserva.objects.create(
            terminal_id=terminal.id,
            filial_id=filial.id,
            numero=1,
            serie=1,
            request_id=req_id,
        )
        print("DEBUG: Reserva de número criada para request_id:", req_id)

    client = _make_client_for_schema(schema1, user)
    print("DEBUG: Client criado para schema:", schema1)
    # Pré-emissão via endpoint real
    payload = {
        "itens": [],
        "total": 10,
        "observacao": "Pré-emissão via view para teste emitir_nfce_view",
    }
    pre_resp = _post_pre_emissao(client, req_id, payload)
    assert pre_resp.status_code in (200, 201), pre_resp.content
    print("DEBUG: Pré-emissão realizada com sucesso para request_id:", req_id)
    # Monkeypatch: sempre usar FakeSefazClient na emissão
    import fiscal.views.nfce_emissao_views as nfce_views

    def _fake_get_sefaz_client_for_filial(f):
        return FakeSefazClient()

    monkeypatch.setattr(
        nfce_views, "get_sefaz_client_for_filial", _fake_get_sefaz_client_for_filial
    )

    host = f"tenant-{schema1}.test.local"
    print("DEBUG:HOST:", host)
    # Chamada de emissão
    resp = client.post(
        "/api/v1/fiscal/nfce/emitir",
        data={"request_id": str(req_id)},
        format="json",
        HTTP_HOST=host,
    )
    print("DEBUG: Resposta da emissão:", resp.status_code, resp.content)
    print("DEBUG: Emissão via view realizada para request_id:", req_id)
    assert resp.status_code == 200, resp.content
    body = resp.json()

    # Valida coerência com o documento persistido
    with schema_context(schema1):
        docs = NfceDocumento.objects.filter(request_id=req_id)
        print("DEBUG: Docs encontrados:", docs.count())
        print("DEBUG: Docs queryset:", docs.query)
        assert docs.count() == 1
        doc = docs.first()
        print("DEBUG: Docs:", doc)
        assert body["numero"] == doc.numero
        assert body["serie"] == doc.serie
        assert body["filial_id"] == str(doc.filial_id)
        assert body["terminal_id"] == str(doc.terminal_id)
        assert body["status"] == doc.status
        assert body["chave_acesso"] == doc.chave_acesso


# -------------------------------------------------------------------------
# 2) Erro genérico ANTES de existir documento → FISCAL_5999
# -------------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", "testserver"],
)
def test_emitir_nfce_view_erro_sem_documento_retorna_fiscal_5999(two_tenants_with_admins, monkeypatch):
    schema1 = two_tenants_with_admins["schema1"]

    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")

    print("DEBUG: Iniciando teste de emitir_nfce_view com erro sem documento (schema=%s)." % schema1)

    with schema_context(schema1):
        user = User.objects.create_user(
            username="oper-view-erro",
            password="123456",
        )
        print("DEBUG: Usuário criado:", user)


        filial = Filial.objects.first()
        assert filial is not None, "Nenhuma Filial existente no tenant de teste."
        print("DEBUG: Filial existente:", filial)
        _ensure_a1_valid(filial)

        terminal = Terminal.objects.create(
            identificador="TERM-VIEW-ERR",
            filial=filial,
            ativo=True,
        )

        if hasattr(user, "userfilial_set"):
            user.userfilial_set.create(filial=filial)

        req_id = uuid.uuid4()
        NfceNumeroReserva.objects.create(
            terminal_id=terminal.id,
            filial_id=filial.id,
            numero=1,
            serie=1,
            request_id=req_id,
        )

    client = _make_client_for_schema(schema1, user)

    payload = {
        "itens": [],
        "total": 5,
        "observacao": "Teste erro sem doc",
    }
    pre_resp = _post_pre_emissao(client, req_id, payload)
    assert pre_resp.status_code in (200, 201), pre_resp.content

    import fiscal.views.nfce_emissao_views as nfce_views

    # Aqui simulamos uma falha ANTES da service persistir qualquer documento
    def _fake_emitir_nfce(*, user, request_id, sefaz_client):
        raise RuntimeError("falha genérica antes de qualquer documento")

    monkeypatch.setattr(nfce_views, "emitir_nfce", _fake_emitir_nfce)

    resp = client.post(
        "/api/v1/fiscal/nfce/emitir/",
        data={"request_id": str(req_id)},
        format="json",
    )

    # DRF converte APIException em HTTP 500 por padrão
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "FISCAL_5999"
    assert "Erro ao comunicar com a SEFAZ" in body["message"]

    # E não deve ter sido criado nenhum NfceDocumento
    with schema_context(schema1):
        assert not NfceDocumento.objects.filter(request_id=req_id).exists()


# -------------------------------------------------------------------------
# 3) Erro genérico DEPOIS de existir documento → fallback por request_id
# -------------------------------------------------------------------------
@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", "testserver"],
)
def test_emitir_nfce_view_quando_servico_falha_apos_persistencia_usa_fallback(two_tenants_with_admins, monkeypatch):
    schema1 = two_tenants_with_admins["schema1"]

    User = get_user_model()
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        user = User.objects.create_user(
            username="oper-view-fallback",
            password="123456",
        )

        filial = Filial.objects.first()
        assert filial is not None, "Nenhuma Filial existente no tenant de teste."

        _ensure_a1_valid(filial)

        terminal = Terminal.objects.create(
            identificador="TERM-VIEW-FB",
            filial=filial,
            ativo=True,
        )

        if hasattr(user, "userfilial_set"):
            user.userfilial_set.create(filial=filial)

        req_id = uuid.uuid4()
        NfceNumeroReserva.objects.create(
            terminal_id=terminal.id,
            filial_id=filial.id,
            numero=1,
            serie=1,
            request_id=req_id,
        )

    client = _make_client_for_schema(schema1, user)

    payload = {
        "itens": [],
        "total": 15,
        "observacao": "Teste fallback pós-persistência",
    }
    pre_resp = _post_pre_emissao(client, req_id, payload)
    assert pre_resp.status_code in (200, 201), pre_resp.content

    import fiscal.views.nfce_emissao_views as nfce_views
    import fiscal.services.emissao_service as emissao_service

    # Sempre usar FakeSefazClient na emissão REAL
    def _fake_get_sefaz_client_for_filial(f):
        return FakeSefazClient()

    monkeypatch.setattr(
        nfce_views, "get_sefaz_client_for_filial", _fake_get_sefaz_client_for_filial
    )

    # Fake emitir_nfce da view:
    #  - chama a service REAL (que persiste o documento)
    #  - depois explode, simulando bug pós-persistência
    def _fake_emitir_nfce(*, user, request_id, sefaz_client):
        result = emissao_service.emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=sefaz_client,
        )
        raise RuntimeError("falha proposital após emissão")

    monkeypatch.setattr(nfce_views, "emitir_nfce", _fake_emitir_nfce)

    resp = client.post(
        "/api/v1/fiscal/nfce/emitir/",
        data={"request_id": str(req_id)},
        format="json",
    )

    # ✅ Mesmo com falha pós-emissão, a view deve usar o fallback e responder 200
    assert resp.status_code == 200, resp.content
    body = resp.json()

    with schema_context(schema1):
        doc = NfceDocumento.objects.get(request_id=req_id)

        assert body["numero"] == doc.numero
        assert body["serie"] == doc.serie
        assert body["filial_id"] == str(doc.filial_id)
        assert body["terminal_id"] == str(doc.terminal_id)
        assert body["status"] == doc.status
