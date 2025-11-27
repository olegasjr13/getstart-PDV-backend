
import uuid
from decimal import Decimal

from django.db import models

from produtos.models.produtos_models import Produto
from vendas.models.venda_models import Venda
from django.core.exceptions import ValidationError

class VendaItem(models.Model):
    """
    Item de uma venda (linha do carrinho).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    venda = models.ForeignKey(
        Venda,
        on_delete=models.CASCADE,
        related_name="itens",
        help_text="Venda à qual este item pertence.",
    )

    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name="itens_venda",
        help_text="Produto vendido.",
    )

    descricao = models.CharField(
        max_length=255,
        help_text="Descrição do produto no momento da venda (snapshot).",
    )

    quantidade = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Quantidade vendida.",
    )

    preco_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        help_text="Preço unitário praticado na venda.",
    )

    total_bruto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total bruto do item (quantidade x preço unitário).",
    )

    
    percentual_desconto_aplicado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Percentual de desconto aplicado sobre o preço unitário do produto "
            "neste item. Usado para auditoria e validação de limites."
        ),
    )

    desconto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Valor absoluto de desconto aplicado neste item.",
    )

    motivo_desconto = models.ForeignKey(
        "promocoes.MotivoDesconto",
        on_delete=models.PROTECT,
        related_name="itens_venda_com_desconto",
        null=True,
        blank=True,
        help_text="Motivo do desconto aplicado neste item.",
    )

    desconto_aprovado_por = models.ForeignKey(
        "usuario.User",
        on_delete=models.PROTECT,
        related_name="descontos_itens_aprovados",
        null=True,
        blank=True,
        help_text=(
            "Usuário que aprovou o desconto neste item, quando "
            "foi necessário exceder o limite do operador."
        ),
    )


    total_liquido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total líquido do item (bruto - desconto).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "venda_item"
        verbose_name = "Item de Venda"
        verbose_name_plural = "Itens de Venda"
        indexes = [
            models.Index(fields=["venda"], name="idx_vendaitem_venda"),
        ]

    def __str__(self) -> str:
        return f"Item {self.id} da Venda {self.venda_id}"

    def clean(self):
        errors = {}

        if self.quantidade <= 0:
            errors["quantidade"] = "Quantidade do item deve ser maior que zero."

        if self.total_bruto is not None and self.total_bruto < 0:
            errors["total_bruto"] = "Total bruto do item não pode ser negativo."

        if self.desconto is not None and self.desconto < 0:
            errors["desconto"] = "Desconto do item não pode ser negativo."

        if self.total_liquido is not None and self.total_liquido < 0:
            errors["total_liquido"] = "Total líquido do item não pode ser negativo."

        # Coerência: total_liquido = total_bruto - desconto
        if (
            self.total_bruto is not None
            and self.desconto is not None
            and self.total_liquido is not None
        ):
            esperado = self.total_bruto - self.desconto
            if esperado != self.total_liquido:
                errors["total_liquido"] = (
                    "Total líquido deve ser igual ao total_bruto - desconto."
                )

            if self.total_liquido > self.total_bruto:
                errors["total_liquido"] = (
                    "Total líquido não pode ser maior que o total bruto."
                )

        if (
            self.percentual_desconto_aplicado is not None
            and self.percentual_desconto_aplicado < 0
        ):
            errors["percentual_desconto_aplicado"] = (
                "Percentual de desconto não pode ser negativo."
            )

        if errors:
            raise ValidationError(errors)

