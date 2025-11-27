# tef/models/tef_models.py
import uuid

from django.db import models
from django.core.exceptions import ValidationError


class TefProvider(models.TextChoices):
    SITEF = "sitef", "SiTef"
    OUTRO = "outro", "Outro TEF"


class TefConfig(models.Model):
    """
    Configuração de integração TEF (SITEF ou outros) por Filial
    e opcionalmente por Terminal.

    Regras:
    - Se 'terminal' for NULL: configuração padrão para todos os terminais da filial.
    - Se 'terminal' for preenchido: sobrescreve a config padrão para aquele terminal.
    - unique_together(filial, terminal, provider) garante que não haverá
      duas configs concorrentes para o mesmo escopo.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    filial = models.ForeignKey(
        "filial.Filial",
        on_delete=models.CASCADE,
        related_name="tef_configs",
        help_text="Filial à qual esta configuração TEF pertence.",
    )

    terminal = models.ForeignKey(
        "terminal.Terminal",
        on_delete=models.CASCADE,
        related_name="tef_configs",
        blank=True,
        null=True,
        help_text=(
            "Terminal específico para o qual esta configuração se aplica. "
            "Se vazio, a configuração é considerada padrão para todos os terminais da filial."
        ),
    )

    provider = models.CharField(
        max_length=20,
        choices=TefProvider.choices,
        default=TefProvider.SITEF,
        help_text="Provider TEF utilizado (ex.: SiTef, outro).",
    )

    merchant_id = models.CharField(
        max_length=64,
        help_text="Identificador do lojista/afiliado no TEF (estabelecimento).",
    )
    store_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Identificador da loja/ponto de venda na adquirente/TEF (opcional).",
    )
    endpoint_base = models.URLField(
        blank=True,
        null=True,
        help_text="Endpoint/base da API TEF (quando TEF é IP/HTTP/Cloud).",
    )

    api_key_alias = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text=(
            "Alias/identificador da credencial TEF no cofre de segredos. "
            "Não armazena a chave em texto puro no banco."
        ),
    )

    ativo = models.BooleanField(
        default=True,
        help_text="Indica se esta configuração TEF está ativa.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tef_config"
        verbose_name = "Configuração TEF"
        verbose_name_plural = "Configurações TEF"
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "terminal", "provider"],
                name="uniq_tef_config_filial_terminal_provider",
            ),
        ]
        indexes = [
            models.Index(fields=["filial"], name="idx_tef_config_filial"),
            models.Index(fields=["terminal"], name="idx_tef_config_terminal"),
            models.Index(fields=["provider"], name="idx_tef_config_provider"),
        ]

    def __str__(self) -> str:
        escopo = (
            f"Terminal={self.terminal.identificador}"
            if self.terminal_id
            else "Padrão da Filial"
        )
        return f"[{self.get_provider_display()}] {self.filial.nome_fantasia} - {escopo}"

    # ------------------------------------------------------------------
    # Validações de consistência
    # ------------------------------------------------------------------
    def clean(self):
        errors = {}

        # terminal, se informado, deve pertencer à mesma filial
        if self.terminal and self.terminal.filial_id != self.filial_id:
            errors["terminal"] = (
                "O terminal selecionado não pertence à mesma filial desta configuração TEF."
            )

        # Provider obrigatório
        if not self.provider:
            errors["provider"] = "O provider TEF deve ser informado."

        # Para SITEF, merchant_id é obrigatório. endpoint_base pode ser opcional (depende de infra),
        # mas deixamos a critério da sua arquitetura; aqui forço merchant_id.
        if self.provider == TefProvider.SITEF:
            if not self.merchant_id:
                errors["merchant_id"] = (
                    "Para provider 'SiTef', o campo 'merchant_id' é obrigatório."
                )

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------
    # Helper para obter config efetiva (padrão ou específica por terminal)
    # ------------------------------------------------------------------
    @classmethod
    def get_effective_config(cls, filial, terminal=None, provider=TefProvider.SITEF):
        """
        Obtém a configuração TEF "efetiva" para um dado terminal.
        Regra:
        - Se existir config específica para (filial, terminal, provider, ativo=True), usa ela.
        - Senão, tenta pegar a config padrão da filial (terminal IS NULL).
        - Se não encontrar, retorna None.
        """
        qs = cls.objects.filter(
            filial=filial,
            provider=provider,
            ativo=True,
        )

        if terminal is not None:
            especifica = qs.filter(terminal=terminal).first()
            if especifica:
                return especifica

        return qs.filter(terminal__isnull=True).first()

    def get_tef_config(self, provider=TefProvider.SITEF):
        return TefConfig.get_effective_config(
            filial=self.filial,
            terminal=self.terminal,
            provider=provider,
        )