# produtos/models/codigos_barras_models.py

import uuid

from django.core.validators import RegexValidator
from django.db import models


class ProdutoCodigoBarras(models.Model):
    """
    Códigos de barras adicionais do produto.

    Motivação:
    - Um produto pode ter:
        * EAN principal de venda (cEAN)
        * EAN da unidade tributável (cEANTrib)
        * EAN interno de embalagem, DUN-14, etc.
    - Emissão de NF-e/NFC-e usa cEAN e cEANTrib -> podemos marcar quais são
      os "principais" aqui.

    Observação:
    - O produto continua com seu código interno (SKU) próprio.
    """

    TIPO_CODIGO_CHOICES = (
        ("EAN13", "EAN-13"),
        ("EAN14", "EAN-14 / DUN-14"),
        ("EAN8", "EAN-8"),
        ("INTERNO", "Código interno / proprietário"),
        ("OUTRO", "Outro padrão"),
    )

    FUNCAO_CODIGO_CHOICES = (
        ("COMERCIAL", "Código de barras de venda (cEAN)"),
        ("TRIBUTAVEL", "Código de barras unidade tributável (cEANTrib)"),
        ("AMBOS", "Usado tanto como cEAN quanto cEANTrib"),
        ("OUTRO", "Apenas referência interna / outro uso"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    produto = models.ForeignKey(
        "produtos.Produto",
        on_delete=models.CASCADE,
        related_name="codigos_barras",
        help_text="Produto ao qual este código de barras pertence.",
    )

    codigo = models.CharField(
        max_length=20,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9]{2,20}$",
                message="Código de barras deve conter apenas dígitos.",
            )
        ],
        help_text="Valor literal do código de barras (apenas dígitos).",
    )

    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CODIGO_CHOICES,
        default="EAN13",
        help_text="Tipo de código de barras (EAN-13, EAN-14, interno, etc).",
    )

    funcao = models.CharField(
        max_length=15,
        choices=FUNCAO_CODIGO_CHOICES,
        default="COMERCIAL",
        help_text="Papel principal deste código para NF-e/NFC-e.",
    )

    # Se o código for específico de uma unidade (ex: caixa vs unidade)
    unidade = models.ForeignKey(
        "produtos.UnidadeMedida",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="codigos_barras",
        help_text="Unidade de medida associada a este código, se houver (ex: CX, UN).",
    )

    principal = models.BooleanField(
        default=False,
        help_text=(
            "Indica se este é o código de barras principal do produto "
            "para a função informada."
        ),
    )

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Código de Barras do Produto"
        verbose_name_plural = "Códigos de Barras dos Produtos"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["produto", "codigo"],
                name="uniq_produto_codigo_barras",
            ),
            models.UniqueConstraint(
                fields=["produto", "funcao"],
                condition=models.Q(principal=True),
                name="uniq_principal_por_funcao_produto",
            ),
        ]
        indexes = [
            models.Index(fields=["codigo"], name="idx_prod_cod_barras_codigo"),
            models.Index(fields=["produto", "ativo"], name="idx_prod_cod_barras_ativo"),
            models.Index(
                fields=["produto", "funcao", "ativo"],
                name="idx_pcb_func_atv",  # Nome encurtado
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} ({self.get_tipo_display()}) - {self.produto}"
