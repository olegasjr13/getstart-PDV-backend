# tests/caixa/test_caixa_service.py

import pytest
from decimal import Decimal

from caixa.models import Caixa
from caixa.services.caixa_service import CaixaService, CaixaServiceError


@pytest.mark.django_db
def test_abrir_caixa_em_terminal_que_nao_permite_caixa(terminal_factory, usuario_factory):
    terminal = terminal_factory(abre_fecha_caixa=False)
    operador = usuario_factory()

    with pytest.raises(CaixaServiceError) as exc:
        CaixaService.abrir_caixa(terminal=terminal, operador=operador, saldo_inicial=Decimal("100.00"))

    assert exc.value.code == "TERMINAL_NAO_PERMITE_CAIXA"
    assert Caixa.objects.count() == 0


@pytest.mark.django_db
def test_abrir_segundo_caixa_para_mesmo_terminal(terminal_factory, usuario_factory):
    terminal = terminal_factory(abre_fecha_caixa=True)
    operador = usuario_factory()

    CaixaService.abrir_caixa(terminal=terminal, operador=operador, saldo_inicial=Decimal("0.00"))

    with pytest.raises(CaixaServiceError) as exc:
        CaixaService.abrir_caixa(terminal=terminal, operador=operador, saldo_inicial=Decimal("0.00"))

    assert exc.value.code == "CAIXA_JA_ABERTO"
    assert Caixa.objects.filter(terminal=terminal).count() == 1
