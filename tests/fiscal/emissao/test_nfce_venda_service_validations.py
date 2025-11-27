# tests/fiscal/emissao/test_nfce_venda_service_validations.py

import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from django.apps import apps
from django_tenants.utils import schema_context
from rest_framework.exceptions import ValidationError

from fiscal.services.nfce_venda_service import (
    nfce_pre_emissao,
    emitir_nfce_para_venda,
    _obter_serie_nfce_do_terminal,
)
from vendas.models.venda_models import VendaStatus, TipoDocumentoFiscal
from vendas.models.venda_pagamentos_models import StatusPagamento


# --------------------------------------------------------------------------------------
# HELPERS LOCAIS
# --------------------------------------------------------------------------------------


def _criar_venda_basica(
    *,
    schema: str,
    status: str = VendaStatus.PAGAMENTO_CONFIRMADO,
    documento_fiscal_tipo: str = TipoDocumentoFiscal.NFCE,
    total_liquido: Decimal = Decimal("100.00"),
):
    """
    Cria uma venda mínima para testes de validação de NFC-e.
    NÃO cria pagamentos automaticamente.
    """
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        # Garante que a filial tenha UF (para não interferir em testes que não são sobre UF)
        if not getattr(filial, "uf", None):
            filial.uf = "MG"
            filial.save(update_fields=["uf"])

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_VALIDACOES_NFCE",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo=documento_fiscal_tipo,
            status=status,
            total_bruto=total_liquido,
            total_desconto=Decimal("0.00"),
            total_liquido=total_liquido,
            total_pago=total_liquido,
            total_troco=Decimal("0.00"),
        )

        return venda, operador, filial, terminal


def _adicionar_pagamento(
    *,
    schema: str,
    venda,
    utiliza_tef: bool = False,
    status: str = StatusPagamento.AUTORIZADO,
    valor_solicitado: Decimal = Decimal("100.00"),
    valor_autorizado: Decimal = Decimal("100.00"),
    valor_troco: Decimal = Decimal("0.00"),
):
    VendaPagamentoModel = apps.get_model("vendas", "VendaPagamento")

    with schema_context(schema):
        return VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento_id=None,  # pode ser ajustado se seu modelo obrigar
            utiliza_tef=utiliza_tef,
            status=status,
            valor_solicitado=valor_solicitado,
            valor_autorizado=valor_autorizado,
            valor_troco=valor_troco,
        )


# --------------------------------------------------------------------------------------
# TESTES: VALIDAÇÃO DE VENDA PARA NFC-e (cenários de erro)
# --------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_documento_nao_e_nfce(two_tenants_with_admins):
    """
    Cenário:
      - Venda com documento_fiscal_tipo diferente de NFCE.
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1001.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(
        schema=schema1,
        documento_fiscal_tipo=TipoDocumentoFiscal.NFE,  # inválido para NFC-e
    )

    with schema_context(schema1):
        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1001"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "status_invalido",
    [
        VendaStatus.ABERTA,
        VendaStatus.CANCELADA,
        VendaStatus.ERRO_FISCAL,
    ],
)
def test_nfce_pre_emissao_falha_quando_status_venda_invalido(
    two_tenants_with_admins, status_invalido
):
    """
    Cenário:
      - Venda com status que não permite pré-emissão NFC-e.
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1002.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(
        schema=schema1,
        status=status_invalido,
    )

    with schema_context(schema1):
        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1002"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "total_liquido",
    [
        Decimal("0.00"),
        Decimal("-10.00"),
    ],
)
def test_nfce_pre_emissao_falha_quando_total_liquido_zero_ou_negativo(
    two_tenants_with_admins, total_liquido
):
    """
    Cenário:
      - Venda com total_liquido <= 0.
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1003.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(
        schema=schema1,
        total_liquido=total_liquido,
    )

    with schema_context(schema1):
        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1003"


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_venda_sem_filial(two_tenants_with_admins):
    """
    Cenário:
      - Venda sem filial (filial_id=None).
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1004.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, filial, terminal = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        venda.filial = None
        venda.save(update_fields=["filial"])

        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1004"


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_venda_sem_terminal(two_tenants_with_admins):
    """
    Cenário:
      - Venda sem terminal (terminal_id=None).
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1005.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, filial, terminal = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        venda.terminal = None
        venda.save(update_fields=["terminal"])

        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1005"


# --------------------------------------------------------------------------------------
# TESTES: VALIDAÇÃO DE PAGAMENTOS (cobertura financeira)
# --------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_venda_sem_pagamentos(two_tenants_with_admins):
    """
    Cenário:
      - Venda sem nenhum pagamento associado.
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1006.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1006"


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_pagamentos_sem_autorizacao(two_tenants_with_admins):
    """
    Cenário:
      - Venda com pagamento, mas valor_autorizado = 0 e/ou status != AUTORIZADO.
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1007.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        # pagamento sem valor autorizado (ex.: apenas solicitado)
        _adicionar_pagamento(
            schema=schema1,
            venda=venda,
            status=StatusPagamento.PENDENTE,
            valor_solicitado=Decimal("100.00"),
            valor_autorizado=Decimal("0.00"),
        )

        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    # Aqui validamos apenas o código; a mensagem já foi coberta nos testes anteriores
    assert detail["code"] == "FISCAL_1007"


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_falha_quando_total_autorizado_menor_que_total_liquido(
    two_tenants_with_admins,
):
    """
    Cenário:
      - Venda com total_liquido=100.00.
      - Pagamentos autorizados = 80.00 (sem troco).
    Esperado:
      - nfce_pre_emissao lança ValidationError com code FISCAL_1008.
    """
    schema1 = two_tenants_with_admins["schema1"]

    venda, operador, _, _ = _criar_venda_basica(
        schema=schema1,
        total_liquido=Decimal("100.00"),
    )

    with schema_context(schema1):
        _adicionar_pagamento(
            schema=schema1,
            venda=venda,
            valor_solicitado=Decimal("80.00"),
            valor_autorizado=Decimal("80.00"),
            valor_troco=Decimal("0.00"),
        )

        with pytest.raises(ValidationError) as excinfo:
            nfce_pre_emissao(
                venda=venda,
                operador=operador,
                request_id=str(uuid4()),
            )

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1008"


@pytest.mark.django_db(transaction=True)
def test_nfce_pre_emissao_sucesso_quando_total_autorizado_maior_que_total_liquido(
    two_tenants_with_admins, monkeypatch
):
    """
    Cenário:
      - total_liquido=100.00
      - Pagamento autorizado=120.00, troco=20.00 → efetivo=100.00
    Esperado:
      - nfce_pre_emissao NÃO lança erro de validação.
      - reservar_numero_nfce e criar_pre_emissao são chamados.
    """
    schema1 = two_tenants_with_admins["schema1"]

    from fiscal.services import nfce_venda_service as svc

    venda, operador, _, terminal = _criar_venda_basica(
        schema=schema1,
        total_liquido=Decimal("100.00"),
    )

    with schema_context(schema1):
        _adicionar_pagamento(
            schema=schema1,
            venda=venda,
            valor_solicitado=Decimal("120.00"),
            valor_autorizado=Decimal("120.00"),
            valor_troco=Decimal("20.00"),
        )

        chamadas = {
            "reserva": 0,
            "pre": 0,
        }

        class DummyReserva:
            def __init__(self):
                self.numero = 10
                self.serie = 1
                self.terminal_id = str(terminal.id)
                self.filial_id = str(venda.filial_id)

        class DummyPreResult:
            def __init__(self):
                self.id = "pre-123"
                self.numero = 10
                self.serie = 1

        def fake_reservar_numero_nfce(*args, **kwargs):
            chamadas["reserva"] += 1
            return DummyReserva()

        def fake_criar_pre_emissao(*args, **kwargs):
            chamadas["pre"] += 1
            return DummyPreResult()

        monkeypatch.setattr(svc, "reservar_numero_nfce", fake_reservar_numero_nfce)
        monkeypatch.setattr(svc, "criar_pre_emissao", fake_criar_pre_emissao)

        # não deve lançar exceção
        result = nfce_pre_emissao(
            venda=venda,
            operador=operador,
            request_id=str(uuid4()),
        )

        assert chamadas["reserva"] == 1
        assert chamadas["pre"] == 1
        assert isinstance(result, DummyPreResult)


# --------------------------------------------------------------------------------------
# TESTES: _obter_serie_nfce_do_terminal
# --------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_obter_serie_nfce_terminal_sem_campos_retorna_1_e_log_warning(
    two_tenants_with_admins, caplog
):
    """
    Cenário:
      - Terminal sem atributo 'serie' e sem 'serie_nfce'.
    Esperado:
      - _obter_serie_nfce_do_terminal retorna 1.
      - Emite WARNING em log.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_SEM_SERIE",
            ativo=True,
        )

        # Remove dinamicamente os atributos se existirem
        for attr in ["serie", "serie_nfce"]:
            if hasattr(terminal, attr):
                delattr(terminal, attr)

        caplog.set_level("WARNING")

        serie = _obter_serie_nfce_do_terminal(terminal)

        assert serie == 1
        assert any("Terminal sem série NFC-e configurada" in m for m in caplog.text)


@pytest.mark.django_db(transaction=True)
def test_obter_serie_nfce_terminal_com_serie_valida(two_tenants_with_admins):
    """
    Cenário:
      - Terminal com série configurada.
    Esperado:
      - _obter_serie_nfce_do_terminal retorna o valor configurado (int).
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_SERIE_10",
            ativo=True,
        )
        terminal.serie = 10

        serie = _obter_serie_nfce_do_terminal(terminal)
        assert serie == 10


@pytest.mark.django_db(transaction=True)
def test_obter_serie_nfce_terminal_com_serie_invalida_dispara_erro(two_tenants_with_admins):
    """
    Cenário:
      - Terminal com série não numérica (ex.: 'ABC').
    Esperado:
      - _obter_serie_nfce_do_terminal lança ValidationError (code FISCAL_1007).
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_SERIE_INVALIDA",
            ativo=True,
        )
        terminal.serie = "ABC"

        with pytest.raises(ValidationError) as excinfo:
            _obter_serie_nfce_do_terminal(terminal)

    detail = excinfo.value.detail
    assert detail["code"] == "FISCAL_1007"


# --------------------------------------------------------------------------------------
# TESTES: emitir_nfce_para_venda (orquestração / request_id)
# --------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_para_venda_gera_request_id_quando_none(
    two_tenants_with_admins, monkeypatch
):
    """
    Cenário:
      - Chamada emitir_nfce_para_venda sem request_id.
    Esperado:
      - Serviço gera um UUID.
      - nfce_pre_emissao e emitir_nfce recebem o MESMO request_id.
    """
    schema1 = two_tenants_with_admins["schema1"]
    from fiscal.services import nfce_venda_service as svc

    venda, operador, _, _ = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        _adicionar_pagamento(schema=schema1, venda=venda)

        chamadas = {
            "pre": [],
            "emit": [],
        }

        class DummySefazClient:
            pass

        class DummyPreResult:
            def __init__(self):
                self.id = "pre-001"
                self.numero = 1
                self.serie = 1

        class DummyEmitResult:
            def __init__(self):
                self.numero = 1
                self.serie = 1
                self.status = "AUTORIZADA"

        def fake_nfce_pre_emissao(*, venda, operador, request_id):
            chamadas["pre"].append(request_id)
            return DummyPreResult()

        def fake_emitir_nfce(*, user, request_id, sefaz_client):
            chamadas["emit"].append(request_id)
            return DummyEmitResult()

        monkeypatch.setattr(svc, "nfce_pre_emissao", fake_nfce_pre_emissao)
        monkeypatch.setattr(svc, "emitir_nfce", fake_emitir_nfce)

        result = emitir_nfce_para_venda(
            venda=venda,
            operador=operador,
            sefaz_client=DummySefazClient(),
            request_id=None,
        )

        assert isinstance(result, DummyEmitResult)
        assert len(chamadas["pre"]) == 1
        assert len(chamadas["emit"]) == 1

        req_pre = chamadas["pre"][0]
        req_emit = chamadas["emit"][0]

        # Ambos devem ser UUID e iguais
        assert isinstance(req_pre, UUID)
        assert isinstance(req_emit, UUID)
        assert req_pre == req_emit


@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_para_venda_respeita_request_id_informado(
    two_tenants_with_admins, monkeypatch
):
    """
    Cenário:
      - Chamada emitir_nfce_para_venda com request_id explícito.
    Esperado:
      - nfce_pre_emissao e emitir_nfce usam exatamente o mesmo UUID.
    """
    schema1 = two_tenants_with_admins["schema1"]
    from fiscal.services import nfce_venda_service as svc

    venda, operador, _, _ = _criar_venda_basica(schema=schema1)

    with schema_context(schema1):
        _adicionar_pagamento(schema=schema1, venda=venda)

        chamadas = {
            "pre": [],
            "emit": [],
        }

        class DummySefazClient:
            pass

        class DummyPreResult:
            def __init__(self):
                self.id = "pre-002"
                self.numero = 2
                self.serie = 1

        class DummyEmitResult:
            def __init__(self):
                self.numero = 2
                self.serie = 1
                self.status = "AUTORIZADA"

        def fake_nfce_pre_emissao(*, venda, operador, request_id):
            chamadas["pre"].append(request_id)
            return DummyPreResult()

        def fake_emitir_nfce(*, user, request_id, sefaz_client):
            chamadas["emit"].append(request_id)
            return DummyEmitResult()

        monkeypatch.setattr(svc, "nfce_pre_emissao", fake_nfce_pre_emissao)
        monkeypatch.setattr(svc, "emitir_nfce", fake_emitir_nfce)

        req_id = uuid4()

        result = emitir_nfce_para_venda(
            venda=venda,
            operador=operador,
            sefaz_client=DummySefazClient(),
            request_id=req_id,
        )

        assert isinstance(result, DummyEmitResult)
        assert len(chamadas["pre"]) == 1
        assert len(chamadas["emit"]) == 1

        req_pre = chamadas["pre"][0]
        req_emit = chamadas["emit"][0]

        assert req_pre == req_id
        assert req_emit == req_id
