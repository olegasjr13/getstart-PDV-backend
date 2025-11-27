import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.core.exceptions import ValidationError

from produtos.models.produtos_models import Produto
from vendas.models.venda_models import Venda


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

    # Snapshot comercial
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

    # -------------------------------------------------------------------------
    # SNAPSHOT FISCAL DO ITEM (CRÍTICO PARA AUDITORIA / XML)
    # -------------------------------------------------------------------------
    ncm_codigo = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Código NCM aplicado ao item no momento da venda.",
    )

    cest_codigo = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        help_text="Código CEST aplicado ao item no momento da venda, quando aplicável.",
    )

    origem_mercadoria_item = models.CharField(
        max_length=1,
        null=True,
        blank=True,
        help_text="Origem da mercadoria (0–8) capturada no momento da venda.",
    )

    cfop_aplicado = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        help_text="CFOP aplicado a este item na operação.",
    )

    csosn_icms_item = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="CSOSN/CST ICMS aplicado ao item.",
    )

    cst_pis_item = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="CST PIS aplicado ao item.",
    )

    cst_cofins_item = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="CST COFINS aplicado ao item.",
    )

    cst_ipi_item = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="CST IPI aplicado ao item.",
    )

    aliquota_icms_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de ICMS aplicada ao item.",
    )

    aliquota_pis_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de PIS aplicada ao item.",
    )

    aliquota_cofins_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de COFINS aplicada ao item.",
    )

    aliquota_ipi_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de IPI aplicada ao item.",
    )

    aliquota_cbs_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de CBS aplicada ao item.",
    )

    aliquota_ibs_item = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de IBS aplicada ao item.",
    )
    motivo_desconto = models.TextField(
        null=True,
        blank=True,
        help_text="Motivo do desconto aplicado neste item.",
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

    # -------------------------------------------------------------------------
    # HELPERS DE NEGÓCIO
    # -------------------------------------------------------------------------
    def preencher_a_partir_do_produto(self, produto: Produto):
        """
        Preenche o snapshot comercial e fiscal do item a partir do Produto.

        NÃO persiste o registro; o chamador é responsável por chamar save().
        """
        self.produto = produto
        self.descricao = produto.descricao

        # Parâmetros fiscais consolidados do produto
        params = produto.get_parametros_fiscais_base()

        self.ncm_codigo = params["ncm_codigo"]
        self.origem_mercadoria_item = params["origem_mercadoria"]
        self.cfop_aplicado = params["cfop_venda_dentro_estado"]  # regra simplificada

        self.csosn_icms_item = params["csosn_icms"]
        self.cst_pis_item = params["cst_pis"]
        self.cst_cofins_item = params["cst_cofins"]
        self.cst_ipi_item = params["cst_ipi"]

        self.aliquota_icms_item = params["aliquota_icms"]
        self.aliquota_pis_item = params["aliquota_pis"]
        self.aliquota_cofins_item = params["aliquota_cofins"]
        self.aliquota_ipi_item = params["aliquota_ipi"]
        self.aliquota_cbs_item = params["aliquota_cbs"]
        self.aliquota_ibs_item = params["aliquota_ibs"]

        cest = produto.get_cest_principal()
        self.cest_codigo = cest.codigo if cest else None

        return self

    def recalcular_totais(self):
        """
        Recalcula total_bruto, desconto e total_liquido com base em:
        - quantidade
        - preco_unitario
        - percentual_desconto_aplicado (quando informado)
        - desconto (caso percentual não seja informado)
        """
        if self.quantidade is None or self.preco_unitario is None:
            raise ValidationError(
                {
                    "quantidade": "Quantidade deve ser informada para cálculo dos totais.",
                    "preco_unitario": "Preço unitário deve ser informado para cálculo dos totais.",
                }
            )

        total_bruto = (self.quantidade * self.preco_unitario).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        desconto = self.desconto or Decimal("0.00")
        if (
            self.percentual_desconto_aplicado is not None
            and self.percentual_desconto_aplicado > 0
        ):
            desconto = (total_bruto * self.percentual_desconto_aplicado / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        self.total_bruto = total_bruto
        self.desconto = desconto
        self.total_liquido = total_bruto - desconto

        return self

    # -------------------------------------------------------------------------
    # VALIDAÇÕES
    # -------------------------------------------------------------------------
    def clean(self):
        errors = {}

        # Quantidade
        if self.quantidade is None or self.quantidade <= 0:
            errors["quantidade"] = "Quantidade do item deve ser maior que zero."

        # Preço unitário (não aceitamos negativo; zero pode ser usado para brinde/promoção)
        if self.preco_unitario is None or self.preco_unitario < 0:
            errors["preco_unitario"] = "Preço unitário não pode ser negativo."

        # Totais básicos
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

        # Percentual de desconto não pode ser negativo
        if (
            self.percentual_desconto_aplicado is not None
            and self.percentual_desconto_aplicado < 0
        ):
            errors["percentual_desconto_aplicado"] = (
                "Percentual de desconto não pode ser negativo."
            )

        # Motivo obrigatório quando há desconto
        if self.desconto is not None and self.desconto > 0 and not self.motivo_desconto:
            errors["motivo_desconto"] = (
                "Motivo do desconto é obrigatório quando há desconto no item."
            )

        # Validação de limite de desconto vs Produto
        if (
            self.produto
            and self.percentual_desconto_aplicado is not None
            and self.percentual_desconto_aplicado > 0
        ):
            max_desconto = self.produto.desconto_maximo_percentual or Decimal("0.00")
            if (
                self.percentual_desconto_aplicado > max_desconto
                and not self.desconto_aprovado_por
            ):
                errors["percentual_desconto_aplicado"] = (
                    "Desconto acima do máximo do produto exige aprovação explícita."
                )

        # Snapshot fiscal obrigatório quando o item já está vinculado a uma venda
        if self.venda_id and not self.ncm_codigo:
            errors["ncm_codigo"] = (
                "NCM do item deve ser definido (snapshot) ao associar item à venda."
            )

        if errors:
            raise ValidationError(errors)
