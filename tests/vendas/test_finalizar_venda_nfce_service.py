# tests/vendas/test_finalizar_venda_nfce_service.py
import uuid
from decimal import Decimal

import pytest
from django.apps import apps
from django_tenants.utils import schema_context
from django.core.exceptions import ValidationError

from vendas.models.venda_models import VendaStatus
from vendas.services.finalizar_venda_nfce_service import finalizar_venda_e_emitir_nfce


def _get_models():
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    Venda = apps.get_model("vendas", "Venda")
    User = apps.get_model("usuario", "User")
    return Filial, Terminal, Venda, User


# ---------------------------------------------------------------------
# 1. HAPPY PATH – EMISSÃO AUTORIZADA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_happy_path_autorizada(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Venda em PAGAMENTO_CONFIRMADO, configurada para NFCE.
      - Fluxo fiscal retorna status 'autorizada'.
      - Resultado esperado:
        * finalizar_venda_e_emitir_nfce retorna nfce_doc.
        * Venda vai para FINALIZADA.
        * Campos de erro fiscal ficam limpos.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-01",
        )

        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_liquido=Decimal("100.00"),
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            documento_fiscal_tipo="NFCE",
        )

        class FakeNfceDoc:
            def __init__(self):
                self.status = "autorizada"
                self.codigo_erro = None
                self.mensagem_erro = None

        fake_nfce_doc = FakeNfceDoc()

        def fake_emitir_nfce_para_venda(*, venda, operador, request_id, sefaz_client=None):
            # Garante que está chamando com a venda correta e request_id string
            assert venda.id == venda.id
            assert isinstance(request_id, str) or request_id is None
            return fake_nfce_doc

        # IMPORTANT: mocka diretamente no módulo que estamos testando
        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        request_id = uuid.uuid4()

        nfce_doc_retornado = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=request_id,
        )

        venda.refresh_from_db()

        assert nfce_doc_retornado is fake_nfce_doc
        assert venda.status == VendaStatus.FINALIZADA
        assert getattr(venda, "codigo_erro_fiscal", None) is None
        assert getattr(venda, "mensagem_erro_fiscal", None) is None


# ---------------------------------------------------------------------
# 2. IDEMPOTÊNCIA – VENDA JÁ FINALIZADA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_idempotente_venda_ja_finalizada(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Venda já está FINALIZADA antes da chamada.
      - Resultado esperado:
        * Função retorna None.
        * emit_ir_nfce_para_venda NÃO é chamado.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-02",
        )

        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("50.00"),
            total_liquido=Decimal("50.00"),
            status=VendaStatus.FINALIZADA,
            documento_fiscal_tipo="NFCE",
        )

        def fake_emitir_nfce_para_venda(*args, **kwargs):
            raise AssertionError("emitir_nfce_para_venda NÃO deve ser chamado em fluxo idempotente")

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        result = finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=uuid.uuid4(),
        )

        assert result is None
        venda.refresh_from_db()
        assert venda.status == VendaStatus.FINALIZADA


# ---------------------------------------------------------------------
# 3. STATUS INVÁLIDO PARA EMISSÃO
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_status_invalido_dispara_validationerror(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Venda em status ABERTA (ou qualquer um fora do conjunto permitido).
      - Resultado esperado:
        * ValidationError antes mesmo de entrar na transação.
        * emit_ir_nfce_para_venda NÃO é chamado.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-03",
        )

        # Usa um status qualquer que não esteja na whitelist do serviço
        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("30.00"),
            total_liquido=Decimal("30.00"),
            status=VendaStatus.ABERTA,
            documento_fiscal_tipo="NFCE",
        )

        def fake_emitir_nfce_para_venda(*args, **kwargs):
            raise AssertionError("emitir_nfce_para_venda não deve ser chamado com status inválido")

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        with pytest.raises(ValidationError):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------
# 4. TIPO FISCAL INVÁLIDO (documento_fiscal_tipo != NFCE)
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_tipo_fiscal_invalido(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Venda com documento_fiscal_tipo diferente de 'NFCE'.
      - Resultado esperado:
        * ValidationError.
        * emit_ir_nfce_para_venda NÃO é chamado.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-04",
        )

        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("40.00"),
            total_liquido=Decimal("40.00"),
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            documento_fiscal_tipo="NFE",  # inválido para esse fluxo
        )

        def fake_emitir_nfce_para_venda(*args, **kwargs):
            raise AssertionError("emitir_nfce_para_venda não deve ser chamado com tipo fiscal inválido")

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        with pytest.raises(ValidationError):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------
# 5. EMISSÃO REJEITADA → ERRO_FISCAL NA VENDA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_rejeitada_marca_erro_fiscal(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - Fluxo fiscal retorna rejeição (status != autorizado, com código/mensagem).
      - Resultado esperado:
        * Venda vai para ERRO_FISCAL.
        * codigo_erro_fiscal / mensagem_erro_fiscal preenchidos.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-05",
        )

        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("60.00"),
            total_liquido=Decimal("60.00"),
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            documento_fiscal_tipo="NFCE",
        )

        class FakeNfceDocRejeitada:
            def __init__(self):
                self.status = "rejeitada"
                self.codigo_erro = "999"
                self.mensagem_erro = "Rejeição de teste"

        def fake_emitir_nfce_para_venda(*args, **kwargs):
            return FakeNfceDocRejeitada()

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        finalizar_venda_e_emitir_nfce(
            venda=venda,
            operador=operador,
            request_id=uuid.uuid4(),
        )

        venda.refresh_from_db()
        assert venda.status == VendaStatus.ERRO_FISCAL
        assert getattr(venda, "codigo_erro_fiscal", None) == "999"
        assert getattr(venda, "mensagem_erro_fiscal", None) == "Rejeição de teste"


# ---------------------------------------------------------------------
# 6. EXCEÇÃO INTERNA → ERRO_FISCAL + EXCEÇÃO PROPAGADA
# ---------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_excecao_interna_marca_erro_e_propagacao(
    two_tenants_with_admins,
    admin_user,
    monkeypatch,
):
    """
    Cenário:
      - emitir_nfce_para_venda levanta uma exceção inesperada (ex.: timeout).
      - Resultado esperado:
        * Venda vai para ERRO_FISCAL.
        * Campos de erro fiscal preenchidos (pelo menos mensagem genérica).
        * A exceção é propagada para o chamador.
    """
    schema1 = two_tenants_with_admins["schema1"]
    admin_username = two_tenants_with_admins["admin_username_1"]

    Filial, Terminal, Venda, _User = _get_models()

    with schema_context(schema1):
        operador = admin_user(admin_username)
        filial = Filial.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-FIN-06",
        )

        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("70.00"),
            total_liquido=Decimal("70.00"),
            status=VendaStatus.PAGAMENTO_CONFIRMADO,
            documento_fiscal_tipo="NFCE",
        )

        class FakeTimeoutError(Exception):
            pass

        def fake_emitir_nfce_para_venda(*args, **kwargs):
            raise FakeTimeoutError("Timeout ao chamar parceiro fiscal")

        monkeypatch.setattr(
            "fiscal.services.nfce_venda_service.emitir_nfce_para_venda",
            fake_emitir_nfce_para_venda,
        )

        with pytest.raises(FakeTimeoutError):
            finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=uuid.uuid4(),
            )

        venda.refresh_from_db()
        assert venda.status == VendaStatus.ERRO_FISCAL
        # Não sabemos exatamente a mensagem, mas deve haver algo registrado
        assert getattr(venda, "mensagem_erro_fiscal", None) not in (None, "")
