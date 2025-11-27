import uuid
from datetime import timedelta
from typing import Dict, Any

import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_a1_edge_cases import _bootstrap_public_tenant_and_domain
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA
from terminal.models.terminal_models import Terminal
from fiscal.models import NfcePreEmissao, NfceDocumento, NfceAuditoria
from fiscal.services.contingencia_service import regularizar_contingencia_nfce
from fiscal.sefaz_clients import SefazTechnicalError

User = get_user_model()


# =============================================================================
# Fakes de client SEFAZ para regularização
# =============================================================================


class _BaseFakeSefazClient:
    """
    Classe base para fakes de SEFAZ usados apenas nestes testes.

    Todos implementam o método emitir_nfce(pre_emissao=...), que retorna
    um dict compatível com o contrato esperado pela service
    regularizar_contingencia_nfce / emitir_nfce.
    """

    def _build_base_raw(self, *, codigo: int, mensagem: str) -> Dict[str, Any]:
        return {
            "codigo": codigo,
            "mensagem": mensagem,
            "protocolo": f"PROTO-{uuid.uuid4().hex[:8]}",
        }


class FakeSefazClientAutorizada(_BaseFakeSefazClient):
    """
    Simula regularização bem-sucedida (autorização da NFC-e).
    """

    def emitir_nfce(self, *, pre_emissao):
        mensagem = "Autorizado o uso da NFC-e (regularização mock)."
        raw = self._build_base_raw(codigo=100, mensagem=mensagem)
        chave = "NFe" + uuid.uuid4().hex[:41]  # 44 chars

        return {
            "status": "autorizada",
            "chave_acesso": chave,
            "protocolo": raw["protocolo"],
            "xml_autorizado": (
                f"<xml-autorizado-regularizacao numero='{pre_emissao.numero}' "
                f"serie='{pre_emissao.serie}' chave='{chave}' />"
            ),
            "mensagem": mensagem,
            "raw": raw,
        }


class FakeSefazClientRejeitada(_BaseFakeSefazClient):
    """
    Simula regularização rejeitada pela SEFAZ.
    """

    def emitir_nfce(self, *, pre_emissao):
        mensagem = "Rejeição em regularização de NFC-e (mock)."
        raw = self._build_base_raw(codigo=302, mensagem=mensagem)

        # Em rejeição, normalmente não há protocolo/chave válidos para uso,
        # mas ainda assim retornamos campos consistentes.
        return {
            "status": "rejeitada",
            "chave_acesso": None,
            "protocolo": raw["protocolo"],
            "xml_autorizado": None,
            "mensagem": mensagem,
            "raw": raw,
        }


class FakeSefazClientAlwaysTechnicalError(_BaseFakeSefazClient):
    """
    Simula falha técnica durante a regularização.
    """

    def emitir_nfce(self, *, pre_emissao):
        raise SefazTechnicalError(
            message="Falha técnica simulada na regularização (mock).",
            codigo="TECH_FAIL",
            raw={
                "motivo": "Falha técnica simulada na regularização (mock).",
                "contexto": "regularizacao_contingencia",
            },
        )


class FakeSefazClientSpyNoCall(_BaseFakeSefazClient):
    """
    Spy que deve NUNCA ser chamado em cenários de idempotência.
    Se for chamado, o teste falha.
    """

    def __init__(self):
        self.called = False

    def emitir_nfce(self, *, pre_emissao):
        self.called = True
        raise AssertionError("SEFAZ não deveria ser chamado em cenário idempotente.")


# =============================================================================
# Helpers de criação de massa
# =============================================================================


def _marcar_a1_valido(filial: Filial) -> None:
    """
    Marca o certificado A1 da filial como válido, sem depender de helpers externos.
    """
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


def _criar_filial_terminal_usuario():
    # username único para evitar conflito com UNIQUE
    username = f"oper-cont-{uuid.uuid4().hex[:8]}"
    user = User.objects.create_user(username=username, password="123456")

    # CNPJ único por teste (14 dígitos)
    cnpj_num = uuid.uuid4().int % (10**14)
    cnpj = f"{cnpj_num:014d}"

    filial = Filial.objects.create(
        cnpj=cnpj,
        nome_fantasia="Filial Contingência",
        uf="SP",
        csc_id="ID",
        csc_token="TK",
        ambiente="homolog",
    )
    _marcar_a1_valido(filial)

    # identificador de terminal único para não violar UNIQUE
    identificador = f"T-CONT-{uuid.uuid4().hex[:6]}"

    term = Terminal.objects.create(
        identificador=identificador,
        filial_id=filial.id,
        serie=1,
        numero_atual=1,
        ativo=True,
    )

    user.userfilial_set.create(filial_id=filial.id)

    return user, filial, term


def _criar_pre_emissao_e_documento_contingencia(filial, term):
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

    # Documento em contingência pendente, com chave dummy
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
        raw_sefaz_response={"motivo": "Contingência ativada (mock)."},
        mensagem_sefaz="Documento em contingência pendente (mock).",
        ambiente=filial.ambiente,
        uf=filial.uf,
        created_at=timezone.now(),
        em_contingencia=True,
        contingencia_ativada_em=timezone.now(),
        contingencia_motivo="Falha técnica SEFAZ anterior (mock).",
        contingencia_regularizada_em=None,
    )

    return pre, doc


# =============================================================================
# Testes
# =============================================================================


@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_happy_path_autorizada():
    """
    Cenário feliz: documento em contingência é regularizado com sucesso
    (autorizado pela SEFAZ).
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        user, filial, term = _criar_filial_terminal_usuario()
        pre, doc = _criar_pre_emissao_e_documento_contingencia(filial, term)

        sefaz_client = FakeSefazClientAutorizada()

        result = regularizar_contingencia_nfce(
            user=user,
            documento_id=str(doc.id),
            sefaz_client=sefaz_client,
        )

        doc_refrescado = NfceDocumento.objects.get(id=doc.id)

        # Assert do DTO
        assert result.status_antes == "contingencia_pendente"
        assert result.status_depois == "autorizada"
        assert result.em_contingencia_antes is True
        assert result.em_contingencia_depois is False
        assert result.regularizada is True
        assert result.chave_acesso is not None
        assert result.chave_acesso.startswith("NFe")
        assert result.protocolo
        assert result.xml_autorizado is not None
        assert result.mensagem is not None

        # Persistência
        assert doc_refrescado.status == "autorizada"
        assert doc_refrescado.em_contingencia is False
        assert doc_refrescado.contingencia_regularizada_em is not None
        assert doc_refrescado.chave_acesso.startswith("NFe")

        # Auditoria
        assert NfceAuditoria.objects.filter(
            nfce_documento=doc_refrescado,
            tipo_evento="EMISSAO_CONTINGENCIA_REGULARIZADA",
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_rejeitada_cria_auditoria_rejeitada():
    """
    Quando a SEFAZ rejeita a regularização:
      - status final deve ser 'rejeitada_contingencia'
      - documento deixa de estar em contingência pendente
      - auditoria EMISSAO_CONTINGENCIA_REJEITADA é criada.
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        user, filial, term = _criar_filial_terminal_usuario()
        pre, doc = _criar_pre_emissao_e_documento_contingencia(filial, term)

        sefaz_client = FakeSefazClientRejeitada()

        result = regularizar_contingencia_nfce(
            user=user,
            documento_id=str(doc.id),
            sefaz_client=sefaz_client,
        )

        doc_refrescado = NfceDocumento.objects.get(id=doc.id)

        assert result.status_antes == "contingencia_pendente"
        assert result.status_depois == "rejeitada_contingencia"
        assert result.em_contingencia_depois is False
        assert result.regularizada is True

        assert doc_refrescado.status == "rejeitada_contingencia"
        assert doc_refrescado.em_contingencia is False
        assert doc_refrescado.contingencia_regularizada_em is not None

        assert NfceAuditoria.objects.filter(
            nfce_documento=doc_refrescado,
            tipo_evento="EMISSAO_CONTINGENCIA_REJEITADA",
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_idempotente_quando_ja_regularizada():
    """
    Se o documento já não estiver mais em 'contingencia_pendente',
    a service não deve chamar a SEFAZ novamente.
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        user, filial, term = _criar_filial_terminal_usuario()
        pre, doc = _criar_pre_emissao_e_documento_contingencia(filial, term)

        # Simula documento já regularizado
        doc.status = "autorizada"
        doc.em_contingencia = False
        doc.contingencia_regularizada_em = timezone.now()
        doc.save(update_fields=["status", "em_contingencia", "contingencia_regularizada_em"])

        sefaz_client = FakeSefazClientSpyNoCall()

        result = regularizar_contingencia_nfce(
            user=user,
            documento_id=str(doc.id),
            sefaz_client=sefaz_client,
        )

        # SEFAZ não deve ter sido chamado
        assert sefaz_client.called is False

        assert result.status_antes == "autorizada"
        assert result.status_depois == "autorizada"
        assert result.regularizada is False
        assert result.em_contingencia_antes is False
        assert result.em_contingencia_depois is False


@pytest.mark.django_db(transaction=True)
def test_regularizar_contingencia_erro_tecnico_mantem_pendente():
    """
    Quando ocorre falha técnica na SEFAZ durante a regularização,
    o documento deve permanecer em 'contingencia_pendente' e
    em_contingencia=True. A service deve lançar APIException FISCAL_5999.
    """
    from rest_framework.exceptions import APIException

    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        user, filial, term = _criar_filial_terminal_usuario()
        pre, doc = _criar_pre_emissao_e_documento_contingencia(filial, term)

        sefaz_client = FakeSefazClientAlwaysTechnicalError()

        with pytest.raises(APIException) as excinfo:
            regularizar_contingencia_nfce(
                user=user,
                documento_id=str(doc.id),
                sefaz_client=sefaz_client,
            )

        err = excinfo.value
        assert isinstance(err.detail, dict)
        assert err.detail.get("code") == "FISCAL_5999"

        doc_refrescado = NfceDocumento.objects.get(id=doc.id)
        assert doc_refrescado.status == "contingencia_pendente"
        assert doc_refrescado.em_contingencia is True
        assert doc_refrescado.contingencia_regularizada_em is None
