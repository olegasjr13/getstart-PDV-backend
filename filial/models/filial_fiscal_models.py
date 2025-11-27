from django.db import models


from terminal.models.terminal_models import Filial

class TipoContribuinteICMS(models.TextChoices):
    CONTRIBUINTE = "1", "Contribuinte ICMS"
    ISENTO = "2", "Isento"
    NAO_CONTRIBUINTE = "9", "Não contribuinte"


class FilialFiscalConfig(models.Model):
    """
    Configurações fiscais da filial:
    - Inscrições (IE, IM)
    - Regime tributário (CRT)
    - CNAE
    - Tipo de contribuinte ICMS
    """

    filial = models.OneToOneField(
        Filial,
        on_delete=models.CASCADE,
        related_name="fiscal_config",
        help_text="Filial a que esta configuração fiscal pertence.",
    )

    inscricao_estadual = models.CharField(
        max_length=14,
        blank=True,
        help_text="Inscrição Estadual (IE) da filial, se houver.",
    )

    inscricao_municipal = models.CharField(
        max_length=15,
        blank=True,
        help_text="Inscrição Municipal, se emitir NF de serviços.",
    )

    cnae_principal = models.CharField(
        max_length=9,
        blank=True,
        help_text="CNAE fiscal principal (somente números).",
    )

    regime_tributario = models.CharField(
        max_length=1,
        choices=(
            ("1", "Simples Nacional"),
            ("2", "Simples Nacional - excesso de sublimite"),
            ("3", "Regime Normal"),
        ),
        default="1",
        help_text="Regime tributário (CRT) usado na NF-e/NFC-e.",
    )

    tipo_contrib_icms = models.CharField(
        max_length=1,
        choices=TipoContribuinteICMS.choices,
        default=TipoContribuinteICMS.CONTRIBUINTE,
        help_text="Tipo de contribuinte de ICMS da filial.",
    )

    aliquota_pis = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Alíquota de PIS (%) aplicada nas operações da filial.",
    )
    aliquota_cofins = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Alíquota de COFINS (%) aplicada nas operações da filial.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Configuração Fiscal da Filial"
        verbose_name_plural = "Configurações Fiscais das Filiais"

    def __str__(self):
        return f"Fiscal - {self.filial}"
