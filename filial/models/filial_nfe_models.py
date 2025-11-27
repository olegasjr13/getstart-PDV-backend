from django.db import models

from filial.models.filial_models import Filial

class FilialNFeConfig(models.Model):
    """
    Configurações específicas para emissão de NF-e (modelo 55).
    Numeração (série/número) em si está por TERMINAL,
    aqui ficam parâmetros gerais de emissão.
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
        related_name="nfe_config",
        help_text="Filial a que esta configuração de NF-e pertence.",
    )

    ambiente = models.CharField(
        max_length=12,
        choices=AMBIENTE_CHOICES,
        default=AMBIENTE_HOMOLOGACAO,
        help_text="Ambiente padrão de emissão de NF-e (homologação/produção).",
    )

    natureza_operacao_padrao = models.CharField(
        max_length=60,
        default="VENDA DE MERCADORIA",
        help_text="Natureza de operação padrão da NF-e (natOp).",
    )

    versao_layout = models.CharField(
        max_length=5,
        default="4.00",
        help_text="Versão do layout da NF-e utilizada (ex.: 4.00).",
    )

    # Campos extras futuros: tipo de emissão, contingência padrão, etc.

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Configuração NF-e da Filial"
        verbose_name_plural = "Configurações NF-e das Filiais"

    def __str__(self):
        return f"NF-e - {self.filial}"
