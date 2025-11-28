# vendas/services/desconto_service.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from django.db import transaction

from filial.models.filial_models import Filial
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from produtos.models.produtos_models import Produto
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from promocoes.models.motivo_desconto_models import MotivoDesconto
from vendas.models.venda_models import Venda
from vendas.models.venda_item_models import VendaItem

from vendas.services.exceptions import (
    DescontoNaoPermitidoError,
    DescontoRequerAutenticacaoOperadorError,
    DescontoRequerAprovadorError,
    MotivoDescontoObrigatorioError,
)


@dataclass
class LimitesDescontoContexto:
    """
    Representa os limites de desconto disponíveis no contexto da operação.
    """

    limite_produto: Optional[Decimal]
    limite_metodo_pagamento: Optional[Decimal]
    limite_terminal: Optional[Decimal]
    limite_filial: Optional[Decimal]
    limite_operador: Optional[Decimal]
    limite_aprovador: Optional[Decimal]
    limite_contexto: Optional[Decimal]  # primeiro não-nulo em produto -> método -> terminal -> filial

    def menor_limite_contexto_com_operador(self) -> Optional[Decimal]:
        """
        Retorna o limite 'livre' (sem senha) com base no contexto + operador.

        Regras:
        - Se existe limite_contexto:
            * Se operador tiver limite, o corredor livre é MIN(limite_contexto, limite_operador).
            * Senão, o corredor livre é limite_contexto.
        - Se não existe limite_contexto:
            * Não há corredor livre; qualquer desconto dependerá do perfil (operador/aprovador).
        """
        if self.limite_contexto is None:
            return None

        if self.limite_operador is not None:
            return min(self.limite_contexto, self.limite_operador)

        return self.limite_contexto


class DescontoService:
    """
    Serviço responsável por:
    - Calcular os limites de desconto disponíveis no contexto.
    - Validar se um desconto solicitado é permitido.
    - Aplicar o desconto em itens e vendas, recalculando totais.

    ATENÇÃO:
    - Este service NÃO autentica senha de operador/aprovador.
      A autenticação deve ser feita na camada de API/endpoint.
      Aqui, assumimos que, se o chamador passou 'operador_autenticado=True'
      ou um 'aprovador', é porque a senha já foi validada.
    """

    # ------------------------------------------------------------------
    # Cálculo de limites
    # ------------------------------------------------------------------
    @staticmethod
    def _obter_limites_contexto(
        *,
        produto: Optional[Produto],
        metodo_pagamento: Optional[MetodoPagamento],
        terminal: Terminal,
        filial: Filial,
        operador: User,
        aprovador: Optional[User] = None,
    ) -> LimitesDescontoContexto:
        """
        Calcula os limites de desconto disponíveis no contexto atual.

        Ordem de prioridade para o limite de contexto (zona sem senha):
        1) Produto
        2) Método de Pagamento
        3) Terminal
        4) Filial

        Limites de perfil (operador/aprovador) são usados para:
        - Faixa acima do contexto (senha operador)
        - Faixa acima do operador (senha aprovador)
        """

        limite_produto = (
            produto.desconto_maximo_percentual if produto is not None else None
        )

        limite_metodo_pagamento = (
            metodo_pagamento.desconto_maximo_percentual
            if metodo_pagamento is not None
            else None
        )

        limite_terminal = terminal.desconto_maximo_percentual
        limite_filial = filial.desconto_maximo_percentual

        limite_operador = operador.perfil.desconto_maximo_percentual

        limite_aprovador = None
        if aprovador is not None:
            limite_aprovador = aprovador.perfil.desconto_maximo_percentual

        # limite de contexto (zona 'livre' sem senha)
        limite_contexto = None
        for v in [
            limite_produto,
            limite_metodo_pagamento,
            limite_terminal,
            limite_filial,
        ]:
            if v is not None:
                limite_contexto = v
                break
        
        return LimitesDescontoContexto(
            limite_produto=limite_produto,
            limite_metodo_pagamento=limite_metodo_pagamento,
            limite_terminal=limite_terminal,
            limite_filial=limite_filial,
            limite_operador=limite_operador,
            limite_aprovador=limite_aprovador,
            limite_contexto=limite_contexto,
        )
    

    # ------------------------------------------------------------------
    # Validação do desconto solicitado (percentual)
    # ------------------------------------------------------------------
    @staticmethod
    def validar_percentual_desconto(
        *,
        percentual_solicitado: Decimal,
        produto: Optional[Produto],
        metodo_pagamento: Optional[MetodoPagamento],
        terminal: Terminal,
        filial: Filial,
        operador: User,
        aprovador: Optional[User] = None,
    ) -> Tuple[str, LimitesDescontoContexto]:
        """
        Valida se um percentual de desconto é permitido no contexto.

        Retorna uma tupla (nivel_aprovacao, limites_contexto), onde:
        - nivel_aprovacao:
            * "livre"        -> até limite de contexto (só motivo, sem senha)
            * "operador"     -> exige senha do operador
            * "aprovador"    -> exige senha/validação do aprovador
        - limites_contexto: objeto LimitesDescontoContexto usado na decisão.

        Lança:
        - DescontoNaoPermitidoError se o desconto é totalmente proibido.
        """
        D = percentual_solicitado

        if D <= 0:
            # Tecnicamente, não é "desconto"; chamador deve tratar isso antes.
            raise DescontoNaoPermitidoError(
                "Percentual de desconto deve ser maior que zero.",
                percentual_solicitado=D,
            )

        limites = DescontoService._obter_limites_contexto(
            produto=produto,
            metodo_pagamento=metodo_pagamento,
            terminal=terminal,
            filial=filial,
            operador=operador,
            aprovador=aprovador,
        )

        # Se absolutamente ninguém tem limite:
        if (
            limites.limite_contexto is None
            and limites.limite_operador is None
            and limites.limite_aprovador is None
        ):
            raise DescontoNaoPermitidoError(
                "Nenhum limite de desconto está configurado (produto, método, terminal, filial ou usuários). "
                "Desconto não é permitido.",
                percentual_solicitado=D,
            )

        # 1) Zona "livre" (somente motivo, sem senha)
        corredor_livre = limites.menor_limite_contexto_com_operador()
        if corredor_livre is not None and D <= corredor_livre:
            return "livre", limites

        # 2) Zona que exige senha do operador (até o limite do operador)
        if limites.limite_operador is not None and D <= limites.limite_operador:
            # Desconto é permitido, mas requer autenticação do operador
            raise DescontoRequerAutenticacaoOperadorError(
                mensagem=(
                    "Desconto acima do limite de contexto. "
                    "É necessária autenticação (senha) do operador para conceder este percentual."
                ),
                percentual_solicitado=D,
                limite_operador=limites.limite_operador,
            )

        # 3) Zona que exige aprovador (supervisor/gerente)
        if limites.limite_aprovador is not None and D <= limites.limite_aprovador:
            raise DescontoRequerAprovadorError(
                mensagem=(
                    "Desconto acima do limite do operador. "
                    "É necessária aprovação de um usuário com limite maior (aprovador)."
                ),
                percentual_solicitado=D,
                limite_aprovador=limites.limite_aprovador,
            )

        # 4) Acima de todos os limites -> proibido
        raise DescontoNaoPermitidoError(
            "Percentual de desconto solicitado excede todos os limites configurados "
            "(contexto, operador e aprovador).",
            percentual_solicitado=D,
        )
    
    # ------------------------------------------------------------------
    # Aplicação de desconto total de venda
    # ------------------------------------------------------------------
    
    @staticmethod
    @transaction.atomic
    def aplicar_desconto_total_venda(
        *,
        venda: "Venda",
        valor_desconto: Decimal,
        operador: User,
        motivo: Optional[MotivoDesconto],
        metodo_pagamento: Optional[MetodoPagamento] = None,
        aprovador: Optional[User] = None,
        operador_autenticado: bool = False,
        aprovador_autenticado: bool = False,
        salvar: bool = True,
    ) -> "Venda":
        """
        Aplica um desconto no TOTAL da venda, redistribuindo proporcionalmente
        entre os itens com base no total_bruto de cada item.

        Regras:
        - valor_desconto > 0  => desconto
        - valor_desconto == 0 => não faz nada
        - valor_desconto < 0  => acréscimo (desconto negativo)
        - Respeita os mesmos limites de desconto já usados em aplicar_desconto_item.
        - Atualiza desconto/total_liquido em cada item.
        - Recalcula os totais da venda ao final.
        """
        from decimal import Decimal as D  # segue o padrão já usado no arquivo

        # Se não há desconto algum, não faz nada
        if valor_desconto == D("0.00"):
            return venda

        itens = list(venda.itens.all())
        if not itens:
            raise ValueError("Não é possível aplicar desconto total em uma venda sem itens.")

        # Total bruto atual a partir dos itens (fonte de verdade)
        total_bruto = D("0.00")
        for it in itens:
            total_bruto += it.total_bruto

        if total_bruto <= D("0.00"):
            raise ValueError(
                "Total bruto da venda deve ser maior que zero para aplicar desconto total."
            )

        valor_desconto = D(valor_desconto)

        # Desconto total em relação ao total da venda (percentual equivalente)
        percentual_equivalente = (abs(valor_desconto) / total_bruto) * D("100")

        # Motivo é obrigatório para qualquer desconto > 0 (mesma regra do item)
        if percentual_equivalente > D("0.00") and motivo is None:
            # mesmo erro usado em aplicar_desconto_item
            raise MotivoDescontoObrigatorioError()

        # ------------------------------------------------------------------
        # Validação dos limites de desconto, reaproveitando a lógica existente
        # ------------------------------------------------------------------
        try:
            nivel, limites = DescontoService.validar_percentual_desconto(
                percentual_solicitado=percentual_equivalente,
                produto=None,  # desconto no total da venda, não em um produto específico
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )
        except DescontoRequerAutenticacaoOperadorError:
            # Só podemos seguir se operador_autenticado for True
            if not operador_autenticado:
                # Propaga pra camada superior pedir senha do operador
                raise
            nivel = "operador"
            limites = DescontoService._obter_limites_contexto(
                produto=None,
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )
        except DescontoRequerAprovadorError:
            # Só podemos seguir se aprovador_autenticado e aprovador existirem
            if not aprovador_autenticado or aprovador is None:
                # Propaga pra camada superior pedir aprovador/senha
                raise
            nivel = "aprovador"
            limites = DescontoService._obter_limites_contexto(
                produto=None,
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )

        # Se chegou aqui sem exceção, ou ajustamos nivel manualmente acima
        # nivel será "livre", "operador" ou "aprovador"
        # (por enquanto não precisamos usar 'nivel' e 'limites' diretamente,
        # apenas garantir que a validação passou)

        # ------------------------------------------------------------------
        # Redistribuir o desconto entre os itens proporcionalmente ao total_bruto
        # ------------------------------------------------------------------
        desconto_restante = valor_desconto
        total_bruto_restante = total_bruto

        for idx, item in enumerate(itens, start=1):
            if idx < len(itens):
                # Fração proporcional do desconto para este item
                if total_bruto_restante == D("0.00"):
                    desconto_item = D("0.00")
                else:
                    proporcao = item.total_bruto / total_bruto_restante
                    desconto_item = (valor_desconto * proporcao).quantize(
                        D("0.01"), rounding=ROUND_HALF_UP
                    )
            else:
                # Último item: garante que a soma dos descontos bata exatamente com valor_desconto
                desconto_item = desconto_restante

            desconto_restante -= desconto_item
            total_bruto_restante -= item.total_bruto

            novo_total_liquido = item.total_bruto - desconto_item

            if novo_total_liquido < D("0.00"):
                raise DescontoNaoPermitidoError(
                    f"Desconto resultou em valor negativo para o item {item.id}.",
                    percentual_solicitado=percentual_equivalente,
                )

            # Atualiza campos do item (mesma ideia de aplicar_desconto_item)
            item.desconto = (item.total_bruto - novo_total_liquido).quantize(
                D("0.01"), rounding=ROUND_HALF_UP
            )
            item.total_liquido = novo_total_liquido.quantize(
                D("0.01"), rounding=ROUND_HALF_UP
            )

            if item.total_bruto > D("0.00"):
                item.percentual_desconto_aplicado = (
                    (item.desconto / item.total_bruto) * D("100")
                ).quantize(D("0.01"), rounding=ROUND_HALF_UP)
            else:
                item.percentual_desconto_aplicado = D("0.00")

            item.motivo_desconto = motivo
            item.desconto_aprovado_por = aprovador

            item.save(
                update_fields=[
                    "desconto",
                    "total_liquido",
                    "percentual_desconto_aplicado",
                    "motivo_desconto",
                    "desconto_aprovado_por",
                ]
            )

        # Recalcula os totais da venda com base nos itens atualizados
        DescontoService.recalcular_totais_venda(venda=venda, salvar=salvar)

        return venda



    # ------------------------------------------------------------------
    # Aplicação de desconto em ITEM de venda
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def aplicar_desconto_item(
        *,
        venda: Venda,
        item: VendaItem,
        percentual_desconto_aplicado: Decimal,
        operador: User,
        motivo: Optional[MotivoDesconto],
        metodo_pagamento: Optional[MetodoPagamento] = None,
        aprovador: Optional[User] = None,
        operador_autenticado: bool = False,
        aprovador_autenticado: bool = False,
        salvar: bool = True,
    ) -> VendaItem:
        """
        Aplica desconto em um item da venda, obedecendo todas as regras de limite:

        - Usa:
            * Produto (item.produto)
            * Método de pagamento (opcional, se já conhecido)
            * Terminal (venda.terminal)
            * Filial (venda.filial)
            * Perfil do operador
            * Perfil do aprovador (se houver)

        - Sempre exige MOTIVO quando percentual_desconto > 0.
        - Se for zona 'livre' -> não exige senha.
        - Se exigir operador -> operador_autenticado deve ser True.
        - Se exigir aprovador -> aprovador_autenticado deve ser True e aprovador != None.

        Lança:
        - MotivoDescontoObrigatorioError
        - DescontoNaoPermitidoError
        - DescontoRequerAutenticacaoOperadorError
        - DescontoRequerAprovadorError
        """
        from decimal import Decimal as D  # para facilitar

        if percentual_desconto_aplicado <= 0:
            # Zera desconto do item
            item.percentual_desconto_aplicado = Decimal("0.00")
            #item.desconto = D("0.00")
            item.total_liquido = item.total_bruto
            item.motivo_desconto = None
            item.desconto_aprovado_por = None

            if salvar:
                item.save(update_fields=[
                    "percentual_desconto_aplicado",
                    "total_liquido",
                    "motivo_desconto",
                    "desconto_aprovado_por",
                ])
                DescontoService.recalcular_totais_venda(venda)
            return item

        # Motivo é obrigatório para qualquer desconto > 0
        if motivo is None:
            raise MotivoDescontoObrigatorioError()

        # 1) Tentar validar como 'livre' (ou receber exceções para zonas que exigem senha/aprovador)
        try:
            nivel, limites = DescontoService.validar_percentual_desconto(
                percentual_solicitado=percentual_desconto_aplicado,
                produto=item.produto,
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )
        except DescontoRequerAutenticacaoOperadorError as e:
            # Só podemos seguir se operador_autenticado for True
            if not operador_autenticado:
                # Propaga o erro pra camada superior solicitar senha
                raise
            # Operador autenticado -> tratamos como nivel 'operador'
            nivel = "operador"
            limites = DescontoService._obter_limites_contexto(
                produto=item.produto,
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )
        except DescontoRequerAprovadorError as e:
            # Só podemos seguir se aprovador_autenticado e aprovador existirem
            if not aprovador_autenticado or aprovador is None:
                # Propaga o erro pra camada superior solicitar aprovador/senha
                raise
            nivel = "aprovador"
            limites = DescontoService._obter_limites_contexto(
                produto=item.produto,
                metodo_pagamento=metodo_pagamento,
                terminal=venda.terminal,
                filial=venda.filial,
                operador=operador,
                aprovador=aprovador,
            )

        # Se chegou aqui sem exceção, ou ajustamos nivel manualmente acima
        # 'nivel' será "livre", "operador" ou "aprovador"
        # Cálculo do valor de desconto e novos totais do item
        valor_bruto = item.total_bruto
        valor_desconto = (valor_bruto * percentual_desconto_aplicado / D("100")).quantize(
            D("0.01"), rounding=ROUND_HALF_UP
        )
        valor_liquido = (valor_bruto - valor_desconto).quantize(
            D("0.01"), rounding=ROUND_HALF_UP
        )

        if valor_liquido < 0:
            raise DescontoNaoPermitidoError(
                "O desconto resultaria em valor líquido negativo para o item.",
                percentual_solicitado=percentual_desconto_aplicado,
            )

        # Atualizar campos do item
        item.percentual_desconto_aplicado = percentual_desconto_aplicado
        item.total_liquido = valor_liquido
        item.motivo_desconto = motivo

        # Quem aprovou?
        if nivel == "aprovador" and aprovador is not None:
            item.desconto_aprovado_por = aprovador
        elif nivel == "operador":
            # Opcional: registrar o próprio operador como aprovador
            item.desconto_aprovado_por = operador
        else:
            # Zona livre -> nenhum aprovador explícito
            item.desconto_aprovado_por = None

        if salvar:
            item.save(update_fields=[
                "percentual_desconto_aplicado",
                "total_liquido",
                "motivo_desconto",
                "desconto_aprovado_por",
            ])

        # Atualiza totais da venda após o desconto
        if salvar:
            DescontoService.recalcular_totais_venda(venda)

        return item
    
    # ------------------------------------------------------------------
    # Recalcular totais de venda
    # ------------------------------------------------------------------
    @staticmethod
    def recalcular_totais_venda(venda: Venda, salvar: bool = True) -> Venda:
        """
        Recalcula os totais da venda (bruto, desconto, líquido) com base nos itens.

        - total_bruto = soma dos total_bruto dos itens
        - total_desconto = soma dos descontos dos itens
        - total_liquido = total_bruto - total_desconto

        (total_pago e total_troco serão atualizados em outro ponto, após pagamentos.)
        """
        from decimal import Decimal as D

        itens = list(venda.itens.all())
        total_bruto = D("0.00")
        total_desconto = D("0.00")

        for it in itens:
            total_bruto += it.total_bruto
            total_desconto += (it.total_bruto - it.total_liquido)

        total_liquido = (total_bruto - total_desconto).quantize(
            D("0.01"), rounding=ROUND_HALF_UP
        )

        venda.total_bruto = total_bruto
        venda.total_desconto = total_desconto
        venda.total_liquido = total_liquido

        if salvar:
            venda.save(update_fields=["total_bruto", "total_desconto", "total_liquido"])

        return venda
