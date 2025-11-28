import uuid

import pytest
from django.apps import apps
from django_tenants.utils import schema_context
from rest_framework.exceptions import NotFound, PermissionDenied

from fiscal.sefaz_clients import SefazTechnicalError
from fiscal.services.emissao_service import emitir_nfce


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


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
# 1. HAPPY PATH – EMISSÃO AUTORIZADA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_autorizada_cria_documento_e_auditoria(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Quando o parceiro fiscal retorna status 'autorizada', o serviço deve:

    - Criar um NfceDocumento com os dados retornados;
    - Criar um NfceAuditoria com tipo_evento 'EMISSAO_AUTORIZADA';
    - Retornar um EmitirNfceResult consistente com o documento;
    - Não marcar o documento como contingência.
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
        # Evita dependência de certificado real A1
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="PDV-01",
        )

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=1,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "10.00"},
        )
        print("DEBUG pre-emissao criada:", pre)

        class FakeSefazClient:
            def __init__(self):
                self.called_with = None

            def emitir_nfce(self, *, pre_emissao):
                self.called_with = pre_emissao.id
                assert pre_emissao.id == pre.id
                return {
                    "status": "autorizada",
                    "chave_acesso": "12345678901234567890123456789012345678901234",
                    "protocolo": "PROT-123",
                    "xml_autorizado": "<xml>ok</xml>",
                    "mensagem": "Autorizado",
                    "codigo_retorno": "100",
                    "raw": {"codigo_retorno": "100", "mensagem": "Autorizado"},
                }

        client = FakeSefazClient()
        print("DEBUG emitindo NFCE...")
        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )
        print("DEBUG emissão NFCE result:", result)
        # Um único documento criado
        docs = NfceDocumentoModel.objects.filter(request_id=request_id)
        print("DEBUG documentos NFC-e encontrados:", docs.count())
        assert docs.count() == 1
        doc = docs.first()
        assert doc is not None

        assert doc.filial_id == filial.id
        assert doc.terminal_id == terminal.id
        assert doc.numero == 1
        assert doc.serie == 1

        assert doc.status == "autorizada"
        assert doc.chave_acesso == "12345678901234567890123456789012345678901234"
        assert doc.protocolo == "PROT-123"
        assert doc.xml_autorizado == "<xml>ok</xml>"
        assert doc.mensagem_sefaz == "Autorizado"
        assert isinstance(doc.raw_sefaz_response, dict)
        assert doc.raw_sefaz_response.get("codigo_retorno") == "100"

        assert doc.em_contingencia is False

        # Auditoria
        audits = NfceAuditoriaModel.objects.filter(request_id=request_id)
        assert audits.count() == 1
        audit = audits.first()
        assert audit is not None
        assert audit.tipo_evento == "EMISSAO_AUTORIZADA"
        assert audit.codigo_retorno == "100"
        assert audit.mensagem_retorno == "Autorizado"

        # Resultado
        assert result.request_id == str(request_id)
        assert result.numero == 1
        assert result.serie == 1
        assert result.filial_id == str(filial.id)
        assert result.terminal_id == str(terminal.id)
        assert result.status == "autorizada"
        assert result.chave_acesso == doc.chave_acesso
        assert result.protocolo == doc.protocolo
        assert result.xml_autorizado == doc.xml_autorizado
        assert result.em_contingencia is False


# ---------------------------------------------------------------------
# 2. EMISSÃO REJEITADA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_rejeitada_cria_documento_e_auditoria(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Quando o parceiro fiscal retorna uma rejeição de regra fiscal, o serviço deve:

    - Criar NfceDocumento com status 'rejeitada' e sem marcar contingência;
    - Criar NfceAuditoria com tipo_evento 'EMISSAO_REJEITADA';
    - Retornar EmitirNfceResult com em_contingencia=False.
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
            identificador="PDV-02",
        )

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=2,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "50.00"},
        )

        class FakeSefazClientRejected:
            def emitir_nfce(self, *, pre_emissao):
                assert pre_emissao.id == pre.id
                return {
                    "status": "rejeitada",
                    "chave_acesso": None,
                    "protocolo": None,
                    "xml_autorizado": None,
                    "mensagem": "Rejeição de teste",
                    "codigo_retorno": "999",
                    "raw": {"codigo_retorno": "999", "mensagem": "Rejeição de teste"},
                }

        client = FakeSefazClientRejected()

        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs.count() == 1
        doc = docs.first()
        assert doc is not None

        assert doc.status == "rejeitada"
        assert doc.em_contingencia is False
        assert doc.mensagem_sefaz == "Rejeição de teste"

        audits = NfceAuditoriaModel.objects.filter(request_id=request_id)
        assert audits.count() == 1
        audit = audits.first()
        assert audit.tipo_evento == "EMISSAO_REJEITADA"
        assert audit.codigo_retorno == "999"
        assert audit.mensagem_retorno == "Rejeição de teste"

        assert result.status == "rejeitada"
        assert result.em_contingencia is False


# ---------------------------------------------------------------------
# 3. FALHA TÉCNICA – CONTINGÊNCIA PENDENTE
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_falha_tecnica_gera_contingencia_pendente(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Quando o client levanta SefazTechnicalError, o serviço deve:

    - Criar NfceDocumento com status 'contingencia_pendente' e em_contingencia=True;
    - Criar NfceAuditoria com tipo_evento 'EMISSAO_CONTINGENCIA_ATIVADA';
    - Retornar EmitirNfceResult com em_contingencia=True e sem chave/protocolo.
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
            identificador="PDV-03",
        )

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=3,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "99.90"},
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

        assert doc.status == "contingencia_pendente"
        assert doc.em_contingencia is True
        assert doc.chave_acesso is not None  # dummy gerada, mas escondida no DTO
        assert doc.xml_autorizado is None

        audits = NfceAuditoriaModel.objects.filter(request_id=request_id)
        assert audits.count() == 1
        audit = audits.first()
        assert audit.tipo_evento == "EMISSAO_CONTINGENCIA_ATIVADA"

        assert result.em_contingencia is True
        assert result.chave_acesso is None
        assert result.protocolo is None
        assert result.xml_autorizado is None


# ---------------------------------------------------------------------
# 4. IDEMPOTÊNCIA – REUSO DE DOCUMENTO EXISTENTE
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_idempotente_reusa_documento_existente(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Se já existir NfceDocumento para o mesmo request_id, o serviço deve:

    - NÃO chamar o client SEFAZ/parceiro novamente;
    - Reutilizar o documento existente e retornar o DTO correspondente.
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
            identificador="PDV-04",
        )

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=4,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "5.00"},
        )

        # Documento pré-existente (simula emissão anterior/partial)
        existing_doc = NfceDocumentoModel.objects.create(
            filial=filial,
            terminal=terminal,
            numero=4,
            serie=1,
            request_id=request_id,
            chave_acesso="EXISTING-CHAVE",
            protocolo="EXISTING-PROT",
            status="autorizada",
            xml_autorizado="<xml>old</xml>",
            raw_sefaz_response={"codigo_retorno": "100"},
            ambiente="homolog",
            uf=filial.uf,
        )

        class FakeSefazClientShouldNotBeCalled:
            def emitir_nfce(self, *, pre_emissao):
                raise AssertionError("Client SEFAZ não deveria ser chamado em fluxo idempotente")

        client = FakeSefazClientShouldNotBeCalled()

        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=client,
        )

        docs = NfceDocumentoModel.objects.filter(request_id=request_id)
        assert docs.count() == 1
        doc = docs.first()
        assert doc.id == existing_doc.id

        assert result.request_id == str(request_id)
        assert result.chave_acesso == existing_doc.chave_acesso
        assert result.status == existing_doc.status
        assert result.em_contingencia is False


# ---------------------------------------------------------------------
# 5. ERROS DE ENTRADA – PRE-EMISSAO / FILIAL / TERMINAL / PERMISSÃO
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_pre_emissao_inexistente(two_tenants_with_admins, admin_user):
    """
    Se não existir NfcePreEmissao para o request_id, deve levantar NotFound.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        _FilialModel,
        _TerminalModel,
        _NfcePreEmissaoModel,
        _NfceDocumentoModel,
        _NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    with schema_context(schema1):
        user = admin_user(admin_username)

        fake_request_id = uuid.uuid4()

        class DummyClient:
            def emitir_nfce(self, *, pre_emissao):
                raise AssertionError("Não deve ser chamado quando não há pré-emissão")

        with pytest.raises(NotFound):
            emitir_nfce(
                user=user,
                request_id=fake_request_id,
                sefaz_client=DummyClient(),
            )


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_filial_inexistente(two_tenants_with_admins, admin_user, monkeypatch):
    """
    Se a filial referenciada na pré-emissão não existir, deve levantar NotFound (FISCAL_4101).
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        _NfceDocumentoModel,
        _NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        user = admin_user(admin_username)
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial_real = FilialModel.objects.first()
        assert filial_real is not None

        terminal = TerminalModel.objects.create(
            filial=filial_real,
            identificador="PDV-05",
        )

        request_id = uuid.uuid4()
        # Usa um UUID aleatório que não corresponde a nenhuma filial real
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=uuid.uuid4(),
            terminal_id=terminal.id,
            numero=5,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "1.00"},
        )

        class DummyClient:
            def emitir_nfce(self, *, pre_emissao):
                raise AssertionError("Client não deve ser chamado quando filial não existe")

        with pytest.raises(NotFound) as excinfo:
            emitir_nfce(
                user=user,
                request_id=request_id,
                sefaz_client=DummyClient(),
            )

        detail = excinfo.value.detail
        assert isinstance(detail, dict)
        assert detail.get("code") == "FISCAL_4101"


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_terminal_inexistente(two_tenants_with_admins, admin_user, monkeypatch):
    """
    Se o terminal referenciado na pré-emissão não existir, deve levantar NotFound (FISCAL_4102).
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        _NfceDocumentoModel,
        _NfceAuditoriaModel,
        _UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        user = admin_user(admin_username)
        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        # Não cria terminal correspondente ao terminal_id usado na pré-emissão
        fake_terminal_id = uuid.uuid4()

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=fake_terminal_id,
            numero=6,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "1.00"},
        )

        class DummyClient:
            def emitir_nfce(self, *, pre_emissao):
                raise AssertionError("Client não deve ser chamado quando terminal não existe")

        with pytest.raises(NotFound) as excinfo:
            emitir_nfce(
                user=user,
                request_id=request_id,
                sefaz_client=DummyClient(),
            )

        detail = excinfo.value.detail
        assert isinstance(detail, dict)
        assert detail.get("code") == "FISCAL_4102"


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_usuario_sem_permissao_filial(two_tenants_with_admins, monkeypatch):
    """
    Se o usuário não estiver vinculado à filial (UserFilial), deve levantar PermissionDenied.
    """
    schema1 = two_tenants_with_admins["schema1"]

    (
        FilialModel,
        TerminalModel,
        NfcePreEmissaoModel,
        _NfceDocumentoModel,
        _NfceAuditoriaModel,
        UserModel,
    ) = _get_models()

    from fiscal.services import emissao_service as svc

    with schema_context(schema1):
        # Cria usuário sem vínculo em UserFilial
        user = UserModel.objects.create_user(username="user_sem_permissao", password="x")

        monkeypatch.setattr(svc, "_assert_a1_valid", lambda filial: None)

        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="PDV-06",
        )

        request_id = uuid.uuid4()
        pre = NfcePreEmissaoModel.objects.create(
            filial_id=filial.id,
            terminal_id=terminal.id,
            numero=7,
            serie=1,
            request_id=request_id,
            payload={"valor_total": "1.00"},
        )

        class DummyClient:
            def emitir_nfce(self, *, pre_emissao):
                raise AssertionError("Client não deve ser chamado quando usuário não tem permissão")

        with pytest.raises(PermissionDenied) as excinfo:
            emitir_nfce(
                user=user,
                request_id=request_id,
                sefaz_client=DummyClient(),
            )

        detail = excinfo.value.detail
        assert isinstance(detail, dict)
        assert detail.get("code") is not None
