# vendas/services/venda_state_machine.py

from __future__ import annotations

import logging
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction

from vendas.models.venda_models import Venda, VendaStatus

logger = logging.getLogger(__name__)


# Matriz de transições permitidas, baseada nos estados já usados hoje:
# - ABERTA
# - AGUARDANDO_PAGAMENTO
# - PAGAMENTO_CONFIRMADO
# - AGUARDANDO_EMISSAO_FISCAL
# - FINALIZADA
# - ERRO_FISCAL
# (CANCELADA pode existir no model, deixei como estado terminal seguro.)
TRANSICOES_VALIDAS: dict[str, set[str]] = {
    # A venda recém aberta pode ir para:
    # - AGUARDANDO_PAGAMENTO (pagamento parcial)
    # - PAGAMENTO_CONFIRMADO (pagamento total à vista)
    # - CANCELADA (se desistir)
    VendaStatus.ABERTA: {
        VendaStatus.AGUARDANDO_PAGAMENTO,
        VendaStatus.PAGAMENTO_CONFIRMADO,
        getattr(VendaStatus, "CANCELADA", VendaStatus.ABERTA),  # fallback seguro
    },

    # Aguardando pagamento:
    # - pode ir para PAGAMENTO_CONFIRMADO (quitação)
    # - ou CANCELADA
    VendaStatus.AGUARDANDO_PAGAMENTO: {
        VendaStatus.PAGAMENTO_CONFIRMADO,
        getattr(VendaStatus, "CANCELADA", VendaStatus.AGUARDANDO_PAGAMENTO),
    },

    # Pagamento confirmado:
    # - pode ir para AGUARDANDO_EMISSAO_FISCAL (quando for emitir NFC-e)
    # - ou CANCELADA (algum fluxo futuro)
    VendaStatus.PAGAMENTO_CONFIRMADO: {
        VendaStatus.AGUARDANDO_EMISSAO_FISCAL,
        getattr(VendaStatus, "CANCELADA", VendaStatus.PAGAMENTO_CONFIRMADO),
    },

    # Aguardando emissão fiscal:
    # - pode ir para FINALIZADA (NFC-e autorizada)
    # - ou ERRO_FISCAL (rejeição/erro)
    VendaStatus.AGUARDANDO_EMISSAO_FISCAL: {
        VendaStatus.FINALIZADA,
        VendaStatus.ERRO_FISCAL,
    },

    # Erro fiscal:
    # - pode ir para FINALIZADA (em caso de reprocesso bem-sucedido)
    # - ou CANCELADA
    VendaStatus.ERRO_FISCAL: {
        VendaStatus.FINALIZADA,
        getattr(VendaStatus, "CANCELADA", VendaStatus.ERRO_FISCAL),
    },

    # Estados terminais: não saem para lugar nenhum
    VendaStatus.FINALIZADA: set(),
    getattr(VendaStatus, "CANCELADA", "CANCELADA"): set(),
}


class VendaStateMachine:
    """
    ÚNICO ponto autorizado a trocar o status da Venda.
    Qualquer lugar que alterar venda.status "na mão" deve ser refatorado
    para passar por aqui (gradativamente).
    """

    @classmethod
    @transaction.atomic
    def mudar_status(
        cls,
        venda: Venda,
        novo_status: str,
        *,
        motivo: str | None = None,
        extra_context: dict | None = None,
        save: bool = True,
    ) -> None:
        """
        - Valida se a transição é permitida (baseado no status atual).
        - É idempotente (se já estiver no status solicitado, não faz nada).
        - Pode ou não salvar a venda (save=True/False).
        """
        status_atual = venda.status

        # Idempotência: não faz nada se já está no status solicitado
        if status_atual == novo_status:
            logger.debug(
                "Transição de status idempotente ignorada.",
                extra={
                    "event": "venda_status_idempotente",
                    "venda_id": venda.id,
                    "status_atual": status_atual,
                    "status_novo": novo_status,
                },
            )
            return

        permitidos: Iterable[str] = TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in permitidos:
            raise ValidationError(
                f"Transição de {status_atual} para {novo_status} não é permitida para venda {venda.id}."
            )

        venda.status = novo_status
        if save:
            venda.save(update_fields=["status"])

        context = {
            "event": "venda_status_transicao",
            "venda_id": venda.id,
            "status_anterior": status_atual,
            "status_novo": novo_status,
            "motivo": motivo,
            "filial_id": getattr(venda, "filial_id", None),
            "terminal_id": getattr(venda, "terminal_id", None),
            "request_id": getattr(venda, "request_id", None),
        }
        if extra_context:
            context.update(extra_context)

        logger.info("venda_status_transicao", extra=context)

    # Atalhos opcionais para melhorar leitura nos services:

    @classmethod
    def para_aguardando_pagamento(cls, venda: Venda, **kwargs) -> None:
        cls.mudar_status(venda, VendaStatus.AGUARDANDO_PAGAMENTO, **kwargs)

    @classmethod
    def para_pagamento_confirmado(cls, venda: Venda, **kwargs) -> None:
        cls.mudar_status(venda, VendaStatus.PAGAMENTO_CONFIRMADO, **kwargs)

    @classmethod
    def para_aguardando_emissao_fiscal(cls, venda: Venda, **kwargs) -> None:
        cls.mudar_status(venda, VendaStatus.AGUARDANDO_EMISSAO_FISCAL, **kwargs)

    @classmethod
    def para_finalizada(cls, venda: Venda, **kwargs) -> None:
        cls.mudar_status(venda, VendaStatus.FINALIZADA, **kwargs)

    @classmethod
    def para_erro_fiscal(cls, venda: Venda, **kwargs) -> None:
        cls.mudar_status(venda, VendaStatus.ERRO_FISCAL, **kwargs)
