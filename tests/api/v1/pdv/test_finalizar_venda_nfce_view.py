# tests/api/v1/pdv/test_finalizar_venda_nfce_view.py

import pytest
from decimal import Decimal
from uuid import uuid4

from django.apps import apps
from django_tenants.utils import schema_context
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from vendas.models.venda_models import VendaStatus

from vendas.api.v1.views import FinalizarVendaNfceView
from vendas.services.finalizar_venda_nfce_service import finalizar_venda_e_emitir_nfce


class DummyNfceDoc:
    def __init__(
        self,
        status="AUTORIZADA",
        codigo_erro=None,
        mensagem_erro=None,
        chave_acesso=None,
        numero=None,
        serie=None,
        protocolo=None,
    ):
        self.status = status
        self.codigo_erro = codigo_erro
        self.mensagem_erro = mensagem_erro
        self.chave_acesso = chave_acesso
        self.numero = numero
        self.serie = serie
        self.protocolo = protocolo


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_view_happy_path(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda paga, tipo NFCE.
    - finalizar_venda_e_emitir_nfce retorna DummyNfceDoc AUTORIZADA.
    - Endpoint deve responder 200 com code=NFCE_EMITIDA.
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
            identificador="CX_API_01",
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

        def fake_finalizar_venda_e_emitir_nfce(*, venda, operador, request_id=None, **kwargs):
            # Simula o fluxo fiscal completo feliz
            venda.status = VendaStatus.FINALIZADA
            venda.codigo_erro_fiscal = None
            venda.mensagem_erro_fiscal = None
            venda.save(update_fields=["status", "codigo_erro_fiscal", "mensagem_erro_fiscal"])
            return DummyNfceDoc(
                status="AUTORIZADA",
                chave_acesso="NFE123",
                numero=1,
                serie=1,
                protocolo="PROTO123",
            )

        monkeypatch.setattr(
            "vendas.api.v1.views.finalizar_venda_e_emitir_nfce",
            fake_finalizar_venda_e_emitir_nfce,
        )

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/v1/pdv/vendas/{venda.id}/finalizar-nfce/",
            {},
            format="json",
            HTTP_X_REQUEST_ID=str(uuid4()),
        )
        force_authenticate(request, user=operador)

        response = FinalizarVendaNfceView.as_view()(request, venda_id=venda.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == "NFCE_EMITIDA"
        assert response.data["venda"]["status"] == VendaStatus.FINALIZADA
        assert response.data["nfce"]["status"] == "AUTORIZADA"
        assert response.data["nfce"]["chave_acesso"] == "NFE123"


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_view_erro_validacao_venda(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - finalizar_venda_e_emitir_nfce dispara ValidationError
      (ex.: venda não paga, tipo fiscal inválido).
    - Endpoint deve retornar 400 com code=ERRO_VALIDACAO_VENDA_NFCE.
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
            identificador="CX_API_02",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.AGUARDANDO_PAGAMENTO,
            total_bruto=Decimal("80.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("80.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_finalizar_venda_e_emitir_nfce(*, venda, operador, request_id=None, **kwargs):
            raise DjangoValidationError("Venda não está em status válido para emissão.")

        monkeypatch.setattr(
            "vendas.api.v1.views.finalizar_venda_e_emitir_nfce",
            fake_finalizar_venda_e_emitir_nfce,
        )

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/v1/pdv/vendas/{venda.id}/finalizar-nfce/",
            {},
            format="json",
        )
        force_authenticate(request, user=operador)

        response = FinalizarVendaNfceView.as_view()(request, venda_id=venda.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "ERRO_VALIDACAO_VENDA_NFCE"
        assert str(venda.id) == response.data["venda_id"]


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_view_erro_interno_fiscal(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - finalizar_venda_e_emitir_nfce lança exceção inesperada (ex.: timeout SEFAZ),
      mas internamente já marcou a venda como ERRO_FISCAL.
    - Endpoint deve retornar 502 com code=ERRO_INTERNO_FISCAL, incluindo status da venda.
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
            identificador="CX_API_03",
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
            codigo_erro_fiscal=None,
            mensagem_erro_fiscal=None,
        )

        def fake_finalizar_venda_e_emitir_nfce(*, venda, operador, request_id=None, **kwargs):
            # Simula o comportamento do service: marca erro fiscal e depois levanta exceção
            venda.status = VendaStatus.ERRO_FISCAL
            venda.mensagem_erro_fiscal = "Falha interna ao emitir NFC-e. Ver logs."
            venda.save(update_fields=["status", "mensagem_erro_fiscal"])
            raise RuntimeError("Timeout ao chamar SEFAZ")

        monkeypatch.setattr(
            "vendas.api.v1.views.finalizar_venda_e_emitir_nfce",
            fake_finalizar_venda_e_emitir_nfce,
        )

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/v1/pdv/vendas/{venda.id}/finalizar-nfce/",
            {},
            format="json",
        )
        force_authenticate(request, user=operador)

        response = FinalizarVendaNfceView.as_view()(request, venda_id=venda.id)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.data["code"] == "ERRO_INTERNO_FISCAL"
        assert response.data["venda"]["status"] == VendaStatus.ERRO_FISCAL
        assert "Falha interna" in (response.data["venda"]["mensagem_erro_fiscal"] or "")


@pytest.mark.django_db(transaction=True)
def test_finalizar_venda_nfce_view_idempotente_venda_ja_finalizada(two_tenants_with_admins, monkeypatch):
    """
    Cenário:
    - Venda já está FINALIZADA antes de chamar o endpoint (ex.: reenvio por erro de rede).
    - finalizar_venda_e_emitir_nfce retorna None (idempotência).
    - Endpoint deve retornar 200 NFCE_EMITIDA com nfce=None, status_venda=FINALIZADA.
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
            identificador="CX_API_04",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.FINALIZADA,
            total_bruto=Decimal("60.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("60.00"),
            total_pago=Decimal("60.00"),
            total_troco=Decimal("0.00"),
        )

        def fake_finalizar_venda_e_emitir_nfce(*, venda, operador, request_id=None, **kwargs):
            # Imita exatamente o comportamento idempotente que implementamos no service: retorna None
            return None

        monkeypatch.setattr(
            "vendas.api.v1.views.finalizar_venda_e_emitir_nfce",
            fake_finalizar_venda_e_emitir_nfce,
        )

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/v1/pdv/vendas/{venda.id}/finalizar-nfce/",
            {},
            format="json",
        )
        force_authenticate(request, user=operador)

        response = FinalizarVendaNfceView.as_view()(request, venda_id=venda.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == "NFCE_EMITIDA"
        assert response.data["venda"]["status"] == VendaStatus.FINALIZADA
        assert response.data["nfce"] is None
