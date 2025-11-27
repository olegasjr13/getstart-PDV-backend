
import uuid
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from vendas.models.venda_models import Venda


class StatusPagamento(models.TextChoices):
    PENDENTE = "PEN", "Pendente"
    AUTORIZADO = "AUT", "Autorizado"   # aprovado (dinheiro/TEF)
    NEGADO = "NEG", "Negado"
    CANCELADO = "CAN", "Cancelado"     # cancelado antes de autorizar
    ESTORNADO = "EST", "Estornado"     # estorno depois de autorizado
    ERRO = "ERR", "Erro de Processamento"


class VendaPagamento(models.Model):
    """
    Representa um pagamento vinculado a uma venda.

    - Permite múltiplos pagamentos por venda (mix de métodos).
    - Armazena valor_solicitado, valor_autorizado e eventual troco.
    - Dados TEF ficam em uma model separada (TefTransacao).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    venda = models.ForeignKey(
        Venda,
        on_delete=models.CASCADE,
        related_name="pagamentos",
        help_text="Venda à qual este pagamento pertence.",
    )

    metodo_pagamento = models.ForeignKey(
        MetodoPagamento,
        on_delete=models.PROTECT,
        related_name="pagamentos",
        help_text="Método de pagamento utilizado.",
    )

    # Valor solicitado pelo operador para este pagamento
    valor_solicitado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Valor solicitado pelo operador para este pagamento.",
    )

    # Valor efetivamente autorizado (pode ser igual ao solicitado ou truncado ao saldo)
    valor_autorizado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor efetivamente autorizado para este pagamento.",
    )

    # Troco gerado especificamente neste pagamento (se aplicável)
    valor_troco = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Parte do valor que retornou como troco neste pagamento.",
    )

    status = models.CharField(
        max_length=3,
        choices=StatusPagamento.choices,
        default=StatusPagamento.PENDENTE,
        db_index=True,
        help_text="Status do pagamento no fluxo de autorização.",
    )

    utiliza_tef = models.BooleanField(
        default=False,
        help_text="Snapshot se o método utilizava TEF no momento do pagamento.",
    ) 

    nsu_host = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="NSU/identificador da transação no host/adquirente.",
    )

    mensagem_retorno = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Mensagem resumida do retorno da adquirente/TEF ou de validação.",
    )
    codigo_retorno = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        help_text="Código de retorno da transação TEF.",
    )

    nsu_sitef = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="NSU/identificador da transação no TEF (ex.: SITEF).",
    )

    codigo_autorizacao = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Código de autorização devolvido pela adquirente.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "venda_pagamento"
        verbose_name = "Pagamento de Venda"
        verbose_name_plural = "Pagamentos de Venda"
        indexes = [
            models.Index(fields=["venda"], name="idx_vendapgto_venda"),
            models.Index(fields=["metodo_pagamento"], name="idx_vendapgto_metodo"),
            models.Index(fields=["status"], name="idx_vendapgto_status"),
        ]

    def __str__(self) -> str:
        return f"Pagamento {self.id} da Venda {self.venda_id}"

    def clean(self):
        errors = {}

        if self.valor_solicitado is None or self.valor_solicitado <= 0:
            errors["valor_solicitado"] = "O valor solicitado deve ser maior que zero."

        if self.valor_troco < 0:
            errors["valor_troco"] = "O valor de troco não pode ser negativo."

        # Valor autorizado nunca pode ser negativo
        if self.valor_autorizado is not None and self.valor_autorizado < 0:
            errors["valor_autorizado"] = "O valor autorizado não pode ser negativo."

        # Usa valor_autorizado se preenchido; se não, usa o solicitado como base
        base_valor = (
            self.valor_autorizado
            if self.valor_autorizado is not None
            else self.valor_solicitado
        )
        if self.valor_troco > base_valor:
            errors["valor_troco"] = (
                "O troco não pode ser maior que o valor autorizado/solicitado."
            )

        # Coerência status x valor_autorizado
        if self.status in {StatusPagamento.AUTORIZADO, StatusPagamento.ESTORNADO}:
            if self.valor_autorizado is None:
                errors["valor_autorizado"] = (
                    "Pagamentos autorizados/estornados devem ter 'valor_autorizado' preenchido."
                )
        else:
            # Em outros status, normalmente não esperamos valor_autorizado > 0
            # (pode deixar, mas você pode forçar zerado se quiser)
            pass

        if errors:
            raise ValidationError(errors)


    # Helpers opcionais para facilitar leitura nas regras
    @property
    def eh_autorizado(self) -> bool:
        return self.status == StatusPagamento.AUTORIZADO

    @property
    def eh_estornado(self) -> bool:
        return self.status == StatusPagamento.ESTORNADO

    @property
    def valor_liquido_para_total(self) -> Decimal:
        """
        Valor que deve entrar na composição do total_pago,
        considerando apenas pagamentos autorizados.
        """
        if not self.eh_autorizado:
            return Decimal("0.00")
        #return (self.valor_autorizado or self.valor_solicitado) - self.valor_troco
        return self.valor_autorizado or Decimal("0.00")