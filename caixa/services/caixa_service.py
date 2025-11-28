# caixa/services/caixa_service.py

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from caixa.models import Caixa
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from vendas.models.venda_models import Venda
from vendas.models.venda_pagamentos_models import VendaPagamento
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento

logger = logging.getLogger(__name__)


class CaixaServiceError(Exception):
    """Erros de negócio do módulo de caixa."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class CaixaService:
    @staticmethod
    @transaction.atomic
    def abrir_caixa(*, terminal: Terminal, operador: User, saldo_inicial: Decimal) -> Caixa:
        """
        Abre um novo caixa para o terminal informado.

        Regras:
        - Terminal precisa ter abre_fecha_caixa=True.
        - Só pode haver um caixa ABERTO por terminal.
        - Usa select_for_update para evitar condição de corrida.
        """

        terminal = Terminal.objects.select_for_update().get(pk=terminal.pk)

        if not terminal.abre_fecha_caixa:
            raise CaixaServiceError("TERMINAL_NAO_PERMITE_CAIXA", "Terminal não suporta fluxo de abre/fecha caixa.")

        existe_aberto = Caixa.objects.filter(
            terminal=terminal,
            status=Caixa.Status.ABERTO,
        ).exists()

        if existe_aberto:
            raise CaixaServiceError("CAIXA_JA_ABERTO", "Já existe um caixa aberto para este terminal.")

        caixa = Caixa.objects.create(
            filial=terminal.filial,
            terminal=terminal,
            operador_abertura=operador,
            saldo_inicial=saldo_inicial,
            aberto_em=timezone.now(),
        )

        logger.info(
            "caixa_aberto",
            extra={
                "event": "caixa_aberto",
                "filial_id": str(terminal.filial_id),
                "terminal_id": str(terminal.id),
                "caixa_id": str(caixa.id),
                "operador_id": operador.id,
                "saldo_inicial": float(saldo_inicial),
            },
        )
        return caixa

    @staticmethod
    def _calcular_saldo_dinheiro(caixa: Caixa) -> Decimal:
        """
        Calcula o saldo em dinheiro esperado para o período do caixa.

        Regra inicial (pode ser evoluída depois):
        - Somar pagamentos em DINHEIRO das vendas associadas ao terminal/filial
          no período deste caixa.
        - Subtrair sangrias e somar suprimentos.
        """
        # Aqui, por enquanto, usamos created_at do BaseModel de Venda como corte.
        vendas = Venda.objects.filter(
            filial=caixa.filial,
            terminal=caixa.terminal,
            created_at__gte=caixa.aberto_em,
            # se quiser, podemos cortar por fechado_em quando existir
        )

        metodo_dinheiro = MetodoPagamento.objects.filter(e_dinheiro=True).first()
        if not metodo_dinheiro:
            return Decimal("0.00")

        pagamentos = VendaPagamento.objects.filter(
            venda__in=vendas,
            metodo_pagamento=metodo_dinheiro,
        )

        total_dinheiro = sum((p.valor_pago for p in pagamentos), Decimal("0.00"))

        total_suprimentos = sum((s.valor for s in caixa.suprimentos.all()), Decimal("0.00"))
        total_sangrias = sum((s.valor for s in caixa.sangrias.all()), Decimal("0.00"))

        return caixa.saldo_inicial + total_dinheiro + total_suprimentos - total_sangrias

    @staticmethod
    @transaction.atomic
    def fechar_caixa(*, caixa: Caixa, operador_fechamento: User, saldo_final_informado: Decimal) -> Caixa:
        """
        Fecha o caixa, calculando o saldo esperado e registrando diferenças.
        """

        caixa = Caixa.objects.select_for_update().get(pk=caixa.pk)

        if caixa.status != Caixa.Status.ABERTO:
            raise CaixaServiceError("CAIXA_NAO_ABERTO", "Caixa não está aberto.")

        saldo_calculado = CaixaService._calcular_saldo_dinheiro(caixa)

        caixa.saldo_final_calculado = saldo_calculado
        caixa.saldo_final_informado = saldo_final_informado
        caixa.diferenca = saldo_final_informado - saldo_calculado
        caixa.status = Caixa.Status.FECHADO
        caixa.operador_fechamento = operador_fechamento
        caixa.fechado_em = timezone.now()
        caixa.save(
            update_fields=[
                "saldo_final_calculado",
                "saldo_final_informado",
                "diferenca",
                "status",
                "operador_fechamento",
                "fechado_em",
            ]
        )

        logger.info(
            "caixa_fechado",
            extra={
                "event": "caixa_fechado",
                "filial_id": str(caixa.filial_id),
                "terminal_id": str(caixa.terminal_id),
                "caixa_id": str(caixa.id),
                "operador_fechamento_id": operador_fechamento.id,
                "saldo_final_calculado": float(saldo_calculado),
                "saldo_final_informado": float(saldo_final_informado),
                "diferenca": float(caixa.diferenca),
            },
        )

        return caixa