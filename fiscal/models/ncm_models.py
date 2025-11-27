import uuid
from decimal import Decimal

from django.db import models

from django.core.validators import RegexValidator
# -------------------------------------------------------------------
# NCM
# -------------------------------------------------------------------

class NCM(models.Model):
    """
    Nomenclatura Comum do Mercosul.

    - Usado em NF-e/NFC-e (tag NCM).
    - Código geralmente com 8 dígitos, mas mantemos flexível (até 10) para
      eventuais exceções ou versões futuras.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        max_length=10,
        db_index=True,
        validators=[RegexValidator(r"^\d{2,10}$", "NCM deve ter apenas dígitos.")],
        help_text="Código NCM (geralmente 8 dígitos, somente números).",
    )
    descricao = models.CharField(max_length=255)

    ex_tipi = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        help_text="EX TIPI quando aplicável.",
    )

    # Alíquotas vigentes (percentuais, ex: 18.00 = 18%)
    aliquota_importacao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de Imposto de Importação associada ao NCM, quando aplicável.",
    )
    aliquota_ipi = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de IPI padrão para este NCM, quando aplicável.",
    )
    aliquota_pis = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota PIS padrão (cumulativo/não cumulativo conforme regime).",
    )
    aliquota_cofins = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota COFINS padrão.",
    )

    # Vigência da linha na tabela oficial
    vigencia_inicio = models.DateField(
        blank=True,
        null=True,
        help_text="Data de início de vigência deste NCM (segundo tabela oficial).",
    )
    vigencia_fim = models.DateField(
        blank=True,
        null=True,
        help_text="Data de fim de vigência (quando revogado/substituído).",
    )
    versao_tabela = models.CharField(
        max_length=20,
        blank=True,
        help_text="Versão/ano da tabela NCM/Tipi utilizada.",
    )

    # Campos de preparação para Reforma Tributária (CBS/IBS a partir de 2026)
    aliquota_cbs_padrao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "Alíquota CBS prevista para este NCM (campo de preparação para novas regras "
            "tributárias a partir de 2026)."
        ),
    )
    aliquota_ibs_padrao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "Alíquota IBS prevista para este NCM (campo de preparação para novas regras "
            "tributárias a partir de 2026)."
        ),
    )

    observacoes = models.TextField(blank=True, default="")

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NCM"
        verbose_name_plural = "NCMs"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo", "vigencia_inicio"],
                name="uniq_ncm_codigo_vigencia_inicio",
            )
        ]


    def __str__(self) -> str:
        return f"{self.codigo} - {self.descricao}"



