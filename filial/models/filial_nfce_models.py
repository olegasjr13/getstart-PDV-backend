from django.db import models

from filial.models.filial_models import Filial

from django.db import models

from filial.models.filial_models import Filial
from django.core.exceptions import ValidationError


class NFCeProvider(models.TextChoices):
    NDD = "ndd", "NDD"
    PROPRIO = "proprio", "API Própria"
    OUTRO = "outro", "Outro Provider"


class FilialNFCeConfig(models.Model):
    """
    Configurações específicas para emissão de NFC-e (modelo 65).
    CSC, ambiente, layout de DANFE NFC-e, etc.
    """

    AMBIENTE_HOMOLOGACAO = "homolog"
    AMBIENTE_PRODUCAO = "producao"
    AMBIENTE_CHOICES = (
        (AMBIENTE_HOMOLOGACAO, "Homologação"),
        (AMBIENTE_PRODUCAO, "Produção"),
    )

    filial = models.OneToOneField(
        Filial,
        on_delete=models.CASCADE,
        related_name="nfce_config",
        help_text="Filial a que esta configuração de NFC-e pertence.",
    )

    ambiente = models.CharField(
        max_length=12,
        choices=AMBIENTE_CHOICES,
        default=AMBIENTE_HOMOLOGACAO,
        help_text="Ambiente padrão de emissão de NFC-e.",
    )

    csc_id = models.CharField(
        max_length=50,
        help_text="Identificador do CSC fornecido pela SEFAZ.",
    )

    csc_token = models.CharField(
        max_length=100,
        help_text="Token do CSC fornecido pela SEFAZ (usado no QR-Code).",
    )

    modelo_impressao = models.CharField(
        max_length=20,
        default="TERMICA80",
        help_text="Configuração padrão de impressão do DANFE NFC-e (uso interno).",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

        # ------------------------------------------------------------------
    # Integração com API externa de emissão NFC-e (ex.: NDD, API própria)
    # ------------------------------------------------------------------
    provider = models.CharField(
        max_length=20,
        choices=NFCeProvider.choices,
        default=NFCeProvider.NDD,
        help_text="Provider de emissão fiscal para NFC-e (NDD, API própria, etc).",
    )

    external_company_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Identificador da empresa na API fiscal externa (ex.: ID na NDD).",
    )

    external_endpoint_base = models.URLField(
        blank=True,
        null=True,
        help_text="URL base da API fiscal externa utilizada para NFC-e nesta filial.",
    )

    external_api_key_alias = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text=(
            "Alias/identificador da credencial no cofre de segredos. "
            "Não armazena a chave em texto puro no banco."
        ),
    )

    def clean(self):
        """
        Validações de consistência da configuração NFC-e, especialmente
        para integração com a API fiscal externa (NDD, API própria, etc).
        """
        errors = {}

        # Se provider for NDD, exigimos external_company_id e external_endpoint_base
        if self.provider == NFCeProvider.NDD:
            if not self.external_company_id:
                errors["external_company_id"] = (
                    "Para provider 'NDD', o campo 'external_company_id' é obrigatório."
                )
            if not self.external_endpoint_base:
                errors["external_endpoint_base"] = (
                    "Para provider 'NDD', o campo 'external_endpoint_base' é obrigatório."
                )

        # Se provider for PROPRIO ou OUTRO, deixamos mais flexível:
        # - Pode usar outros meios de configuração (ex.: parâmetros globais).
        # Aqui só garantimos coerência básica: se preencher endpoint sem provider, é estranho.
        if not self.provider:
            errors["provider"] = "O provider de emissão NFC-e deve ser informado."

        if errors:
            raise ValidationError(errors)



    class Meta:
        verbose_name = "Configuração NFC-e da Filial"
        verbose_name_plural = "Configurações NFC-e das Filiais"

    def __str__(self):
        return f"NFC-e - {self.filial}"
