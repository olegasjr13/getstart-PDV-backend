# tests/fiscal/emissao/test_emissao_nfce_payload_hash.py

import uuid
from copy import deepcopy

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

from fiscal.sefaz_clients import SefazTechnicalError
from fiscal.services.emissao_service import emitir_nfce, _hash_payload


def _get_models():
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    NfcePreEmissaoModel = apps.get_model("fiscal", "NfcePreEmissao")
    NfceDocumentoModel = apps.get_model("fiscal", "NfceDocumento")
    NfceAuditoriaModel = apps.get_model("fiscal", "NfceAuditoria")
    UserModel = apps.get_model("usuario", "User")
    return (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        NfceDocumentoModel,
        NfceAuditoriaModel,
        UserModel,
    )


# ---------------------------------------------------------------------
# 1. EMISSÃO AUTORIZADA – PAYLOAD E HASH PREENCHIDOS
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_autorizada_persiste_payload_e_hash(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Emissão NFC-e normal (autorizada pelo parceiro fiscal).
      - Verifica que:
        * NfceDocumento.payload_enviado == NfcePreEmissao.payload
        * NfceDocumento.hash_payload_enviado == _hash_payload(payload)
        * Auditoria é criada normalmente.

    Esse teste garante que o JSON que o PDV gerou para a nota
    fica imutavelmente registrado no documento fiscal.
    """

    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        NfceDocumentoModel,
        NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        user = admin_user(admin_username)

        # Evita dependência de certificado A1 real
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="PDV-PAYLOAD-01",
        )

        request_id = uuid.uuid4()
        payload_original = {
            "valor_total": "123.45",
            "itens": [
                {
                    "produto_id": "PROD-1",
                    "descricao": "Produto de teste",
                    "quantidade": 2,
                    "preco_unitario": "10.00",
                }
            ],
            "cliente": {"cpf": "12345678909"},
        }

        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=10,
            serie=1,
            request_id=request_id,
            payload=deepcopy(payload_original),
        )

        class FakeSefazClient:
            def __init__(self):
                self.called_with = None

            def emitir_nfce(self, *, pre_emissao):
                self.called_with = pre_emissao.id
                assert pre_emissao.id == pre.id
                return {
                    "status": "autorizada",
                    "chave_acesso": "CHAVE-AUT-123",
                    "protocolo": "PROT-AUT-123",
                    "xml_autorizado": "<xml>autorizada</xml>",
                    "mensagem": "Autorizado com sucesso",
                    "codigo_retorno": "100",
                    "raw": {
                        "codigo_retorno": "100",
                        "mensagem": "Autorizado com sucesso",
                    },
                }

        client = FakeSefazClient()

        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs.count() == 1
        doc = docs.first()
        assert doc is not None

        # Payload e hash
        assert doc.payload_enviado == payload_original
        assert doc.hash_payload_enviado == _hash_payload(payload_original)

        # Confere que outros campos continuam coerentes
        assert doc.status == "autorizada"
        assert doc.chave_acesso == "CHAVE-AUT-123"
        assert doc.protocolo == "PROT-AUT-123"
        assert doc.xml_autorizado == "<xml>autorizada</xml>"

        audits = NfceAuditoriaModel.objects.filter(request_id=request_id)
        assert audits.count() == 1
        audit = audits.first()
        assert audit.tipo_evento == "EMISSAO_AUTORIZADA"

        # DTO também deve refletir emissão autorizada
        assert result.status == "autorizada"
        assert result.em_contingencia is False
        assert result.chave_acesso == doc.chave_acesso
        assert result.protocolo == doc.protocolo


# ---------------------------------------------------------------------
# 2. FALHA TÉCNICA / CONTINGÊNCIA – PAYLOAD E HASH PREENCHIDOS
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_falha_tecnica_persiste_payload_e_hash(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Parceiro fiscal levanta SefazTechnicalError (timeout, queda de rede, etc.)
      - O serviço entra em CONTINGÊNCIA PENDENTE.
      - Mesmo assim, o payload enviado e o hash devem ser gravados
        em NfceDocumento.

    Garante que, em contingência, ainda é possível conciliar depois
    qual foi o conteúdo que o PDV tentou enviar.
    """

    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        NfceDocumentoModel,
        NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        user = admin_user(admin_username)
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="PDV-PAYLOAD-02",
        )

        request_id = uuid.uuid4()
        payload_original = {
            "valor_total": "200.00",
            "itens": [],
            "cliente": None,
        }

        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=11,
            serie=1,
            request_id=request_id,
            payload=deepcopy(payload_original),
        )

        class FakeSefazClientTechError:
            def emitir_nfce(self, *, pre_emissao):
                assert pre_emissao.id == pre.id
                raise SefazTechnicalError(
                    "Timeout ao comunicar com parceiro fiscal",
                    codigo="TECH_TIMEOUT",
                    raw={"detail": "timeout"},
                )

        client = FakeSefazClientTechError()

        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs.count() == 1
        doc = docs.first()
        assert doc is not None

        # Documento em contingência, mas com payload e hash
        assert doc.status == "contingencia_pendente"
        assert doc.em_contingencia is True

        assert doc.payload_enviado == payload_original
        assert doc.hash_payload_enviado == _hash_payload(payload_original)

        audits = NfceAuditoriaModel.objects.filter(request_id=request_id)
        assert audits.count() == 1
        audit = audits.first()
        # O tipo exato pode variar (ex: EMISSAO_CONTINGENCIA_PENDENTE / ATIVADA),
        # aqui garantimos que ao menos há um registro para esse request_id.
        assert audit.request_id == request_id

        # DTO deve refletir contingência, sem expor chave/protocolo
        assert result.em_contingencia is True
        assert result.chave_acesso is None
        assert result.protocolo is None
        assert result.xml_autorizado is None


# ---------------------------------------------------------------------
# 3. IDEMPOTÊNCIA – MESMO PAYLOAD/HASH EM REUSO DE DOCUMENTO
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_idempotente_mantem_mesmo_payload_e_hash(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Primeiro, emite NFC-e autorizada com um payload específico.
      - Depois, chama emitir_nfce novamente com o MESMO request_id.
      - O serviço NÃO chama o parceiro fiscal novamente
        (idempotência por NfceDocumento.request_id).
      - O payload_enviado e o hash_payload_enviado permanecem os mesmos.

    Garante que reprocessamentos idempotentes não alteram o conteúdo
    que foi enviado ao parceiro fiscal.
    """

    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        NfceDocumentoModel,
        _NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        user = admin_user(admin_username)
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="PDV-PAYLOAD-03",
        )

        request_id = uuid.uuid4()
        payload_original = {
            "valor_total": "300.00",
            "itens": [{"produto_id": "P1"}],
        }

        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=12,
            serie=1,
            request_id=request_id,
            payload=deepcopy(payload_original),
        )

        class FakeSefazClient:
            def __init__(self):
                self.calls = 0

            def emitir_nfce(self, *, pre_emissao):
                self.calls += 1
                assert pre_emissao.id == pre.id
                return {
                    "status": "autorizada",
                    "chave_acesso": "CHAVE-IDEMP-123",
                    "protocolo": "PROT-IDEMP-123",
                    "xml_autorizado": "<xml>idem</xml>",
                    "mensagem": "Autorizado",
                    "codigo_retorno": "100",
                    "raw": {"codigo_retorno": "100", "mensagem": "Autorizado"},
                }

        client = FakeSefazClient()

        # 1ª chamada – cria o documento
        result1 = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs1 = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs1.count() == 1
        doc1 = docs1.first()
        assert doc1 is not None

        assert doc1.payload_enviado == payload_original
        assert doc1.hash_payload_enviado == _hash_payload(payload_original)
        assert client.calls == 1

        # 2ª chamada – deve reusar o mesmo documento (idempotência)
        result2 = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs2 = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs2.count() == 1
        doc2 = docs2.first()
        assert doc2.id == doc1.id

        # Payload e hash imutáveis
        assert doc2.payload_enviado == payload_original
        assert doc2.hash_payload_enviado == _hash_payload(payload_original)

        # Client não deve ter sido chamado novamente
        assert client.calls == 1

        # Resultados devem ser consistentes
        assert result1.chave_acesso == result2.chave_acesso
        assert result1.protocolo == result2.protocolo
        assert result1.status == result2.status
