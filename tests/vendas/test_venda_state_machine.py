# tests/vendas/vendas/test_venda_state_machine.py

import pytest

from vendas.models.venda_models import VendaStatus
from vendas.services.venda_state_machine import VendaStateMachine
from core.exceptions import BusinessError


@pytest.mark.django_db
def test_transicao_valida_em_digitacao_para_aguardando_pagamento(venda_factory, caplog):
    venda = venda_factory(status=VendaStatus.EM_DIGITACAO)

    with caplog.at_level("INFO"):
        VendaStateMachine.para_aguardando_pagamento(venda, motivo="teste")

    venda.refresh_from_db()
    assert venda.status == VendaStatus.AGUARDANDO_PAGAMENTO

    registros = [r for r in caplog.records if r.event == "venda_status_transicao"]
    assert registros, "Esperava log de transição de status."
    log = registros[0]
    assert log.status_anterior == VendaStatus.EM_DIGITACAO
    assert log.status_novo == VendaStatus.AGUARDANDO_PAGAMENTO


@pytest.mark.django_db
def test_transicao_invalida_em_digitacao_para_finalizada_dispara_erro(venda_factory):
    venda = venda_factory(status=VendaStatus.EM_DIGITACAO)

    with pytest.raises(BusinessError) as exc:
        VendaStateMachine.para_finalizada(venda, motivo="tentativa inválida")

    assert exc.value.code == "TRANSICAO_DE_ESTADO_INVALIDA"
    venda.refresh_from_db()
    assert venda.status == VendaStatus.EM_DIGITACAO


@pytest.mark.django_db
def test_transicao_idempotente_nao_altera_status(venda_factory, caplog):
    venda = venda_factory(status=VendaStatus.AGUARDANDO_PAGAMENTO)

    with caplog.at_level("DEBUG"):
        VendaStateMachine.para_aguardando_pagamento(venda, motivo="idempotente")

    venda.refresh_from_db()
    assert venda.status == VendaStatus.AGUARDANDO_PAGAMENTO

    # Aqui você pode testar se o log de idempotência foi gerado, se quiser:
    # registros = [r for r in caplog.records if r.event == "venda_status_idempotente"]
    # assert registros
