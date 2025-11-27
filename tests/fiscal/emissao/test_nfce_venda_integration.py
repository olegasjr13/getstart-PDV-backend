# tests/fiscal/emissao/test_nfce_venda_integration.py

import logging
from decimal import Decimal
from uuid import uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from vendas.models.venda_models import VendaStatus
from vendas.services.finalizar_venda_nfce_service import (
    finalizar_venda_e_emitir_nfce,
)

logger = logging.getLogger(__name__)


class DummyNfceDoc:
    """
    Objeto simples para simular um documento fiscal retornado pelo fluxo fiscal,
    sem depender do model real NfceDocumento.

    Usado para testar apenas a orquestração:
    - status (AUTORIZADA, REJEITADA, etc.)
    - codigo_erro
    - mensagem_erro
    """

    def __init__(self, status="AUTORIZADA", codigo_erro=None, mensagem_erro=None):
        self.status = status
        self.codigo_erro = codigo_erro
        self.mensagem_erro = mensagem_erro


# =====================================================================
# 1) HAPPY PATH – VENDA PAGA → NFC-e AUTORIZADA → FINALIZADA
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_para_venda_paga_happy_path(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda com status PAGAMENTO_CONFIRMADO, tipo NFCE e total_liquido=100,00.
    - Serviço fiscal (emitir_nfce_para_venda) é mockado para retornar NFC-e AUTORIZADA.

    Esperado:
    - finalizar_venda_e_emitir_nfce conclui sem erro.
    - Venda muda status para FINALIZADA.
    - Nenhuma mensagem de erro fiscal é gravada.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_01",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("100.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id=None, **kwargs):
            logger.info(
                "fake_emitir_nfce_para_venda chamado. venda_id=%s request_id=%s",
                venda.id,
                request_id,
            )
            return DummyNfceDoc(
                status="AUTORIZADA",
                codigo_erro=None,
                mensagem_erro=None,
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        request_id = uuid4()
        nfce_doc = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=request_id,
        )

        venda.refresh_from_db()

        assert venda.status == VendaStatus.FINALIZADA
        assert getattr(venda, "codigo_erro_fiscal", None) is None
        assert getattr(venda, "mensagem_erro_fiscal", None) is None

        assert nfce_doc.status == "AUTORIZADA"


# =====================================================================
# 2) VENDA NÃO PAGA → BLOQUEIA ANTES DE CHAMAR FISCAL
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_para_venda_nao_paga_dispara_erro(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda ainda em AGUARDANDO_PAGAMENTO.
    - Tentativa de finalizar_venda_e_emitir_nfce deve falhar logo na validação.

    Esperado:
    - ValidationError.
    - Serviço fiscal (emitir_nfce_para_venda) NÃO é chamado.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_02",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.AGUARDANDO_PAGAMENTO,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id=None, **kwargs):
            raise AssertionError(
                "emitir_nfce_para_venda NÃO deveria ser chamado para venda não paga."
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        with pytest.raises(ValidationError):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

        venda.refresh_from_db()
        assert venda.status == VendaStatus.AGUARDANDO_PAGAMENTO


# =====================================================================
# 3) VENDA JÁ FINALIZADA → IDEMPOTÊNCIA
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_para_venda_ja_autorizada_eh_idempotente(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda paga.
    - 1ª chamada: fluxo fiscal retorna NFC-e AUTORIZADA → venda fica FINALIZADA.
    - 2ª chamada: o serviço de finalização deve tratar como idempotente (não chamar fiscal de novo).

    Esperado:
    - 1ª chamada chama emitir_nfce_para_venda uma vez.
    - 2ª chamada NÃO chama emitir_nfce_para_venda.
    - Status da venda permanece FINALIZADA.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_03",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            total_bruto=Decimal("50.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("50.00"),
            total_pago=Decimal("50.00"),
            total_troco=Decimal("0.00"),
        )

        chamadas_fiscal = {"count": 0}

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id=None, **kwargs):
            chamadas_fiscal["count"] += 1
            return DummyNfceDoc(
                status="AUTORIZADA",
                codigo_erro=None,
                mensagem_erro=None,
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        # 1ª chamada -> chama fiscal
        nfce_doc_1 = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=str(uuid4()),
        )
        venda.refresh_from_db()

        assert chamadas_fiscal["count"] == 1
        assert venda.status == VendaStatus.FINALIZADA
        assert nfce_doc_1.status == "AUTORIZADA"

        # 2ª chamada -> idempotente, não chama fiscal de novo
        def fake_emitir_nfce_para_venda_fail(*, venda, operador, request_id=None, **kwargs):
            raise AssertionError(
                "emitir_nfce_para_venda NÃO deveria ser chamado em chamada idempotente."
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda_fail,
        )

        nfce_doc_2 = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=str(uuid4()),
        )

        venda.refresh_from_db()
        assert venda.status == VendaStatus.FINALIZADA
        # nfce_doc_2 pode ser None (implementação idempotente).
        # Se no futuro você quiser retornar um stub, os asserts podem ser ajustados aqui.


# =====================================================================
# 4) NFC-e REJEITADA → VENDA EM ERRO_FISCAL + CÓDIGO/MENSAGEM
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_rejeitada_marca_erro_fiscal_na_venda(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda paga, apta para NFCE.
    - Fluxo fiscal retorna NFC-e REJEITADA (ex.: código 225).

    Esperado:
    - Venda muda status para ERRO_FISCAL.
    - codigo_erro_fiscal e mensagem_erro_fiscal são preenchidos.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_04",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            total_bruto=Decimal("80.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("80.00"),
            total_pago=Decimal("80.00"),
            total_troco=Decimal("0.00"),
            codigo_erro_fiscal=None,
            mensagem_erro_fiscal=None,
        )

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id=None, **kwargs):
            return DummyNfceDoc(
                status="REJEITADA",
                codigo_erro="225",
                mensagem_erro="Rejeição: IE do destinatário não informada",
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        nfce_doc = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=str(uuid4()),
        )

        venda.refresh_from_db()

        assert venda.status == VendaStatus.ERRO_FISCAL
        assert venda.codigo_erro_fiscal == "225"
        assert "Rejeição" in (venda.mensagem_erro_fiscal or "")
        assert nfce_doc.status == "REJEITADA"


# =====================================================================
# 5) ERRO INTERNO / TIMEOUT NA EMISSÃO → ERRO_FISCAL + EXCEÇÃO
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_erro_interno_marca_erro_fiscal_e_propaga(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda paga, apta para NFCE.
    - emitir_nfce_para_venda lança exceção (ex.: timeout, erro de infraestrutura).

    Esperado:
    - finalizar_venda_e_emitir_nfce levanta a mesma exceção.
    - Venda muda status para ERRO_FISCAL.
    - mensagem_erro_fiscal genérica é preenchida.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_05",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            total_bruto=Decimal("120.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("120.00"),
            total_pago=Decimal("120.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_emitir_nfce_para_venda_erro(*, venda, operador, request_id=None, **kwargs):
            raise RuntimeError("Timeout ao chamar SEFAZ")

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda_erro,
        )

        with pytest.raises(RuntimeError, match="Timeout ao chamar SEFAZ"):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

        venda.refresh_from_db()
        assert venda.status == VendaStatus.ERRO_FISCAL
        assert "Falha interna" in (venda.mensagem_erro_fiscal or "")


# =====================================================================
# 6) DOCUMENTO_FISCAL_TIPO INVÁLIDO → VALIDATIONERROR
# =====================================================================

@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_venda_com_documento_fiscal_tipo_invalido(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda paga, mas documento_fiscal_tipo != NFCE (ex.: NFE).
    - finalizar_venda_e_emitir_nfce deve disparar ValidationError.
    - emitir_nfce_para_venda não deve ser chamado.
    """

    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_FISCAL_06",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFE",  # inválido para este fluxo
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            total_bruto=Decimal("60.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("60.00"),
            total_pago=Decimal("60.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id=None, **kwargs):
            raise AssertionError(
                "emitir_nfce_para_venda NÃO deveria ser chamado para documento_fiscal_tipo != NFCE."
            )

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        with pytest.raises(ValidationError):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

        venda.refresh_from_db()
        # Status permanece o mesmo, já que nem entrou no fluxo fiscal
        assert venda.status == VendaStatus.PAGAMENTO_CONFIRMADO

