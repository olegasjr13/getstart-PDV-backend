# empresas/models.py (exemplo – ajuste para o seu app)
import uuid
from django.db import models

# importa Terminal do mesmo arquivo ou do local correto
# from .models import Terminal  # se estiver no mesmo arquivo, não precisa

class DocumentoFiscalSequencia(models.Model):
    """
    Controla a numeração fiscal (série e número atual) por terminal
    e por modelo de documento (NF-e 55, NFC-e 65, etc.).

    Exemplo:
      - Terminal A, modelo 65, série 1 -> numeração NFC-e
      - Terminal A, modelo 55, série 2 -> numeração NF-e
      - Terminal B, modelo 65, série 1 -> outra sequência
    """

    MODELO_NFE = "55"
    MODELO_NFCE = "65"
    MODELO_CHOICES = (
        (MODELO_NFE, "NF-e (55)"),
        (MODELO_NFCE, "NFC-e (65)"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    terminal = models.ForeignKey(
        "Terminal",                            # string p/ evitar problema de ordem
        on_delete=models.PROTECT,
        related_name="sequencias_fiscais",
        help_text="Terminal ao qual esta sequência pertence.",
    )

    modelo = models.CharField(
        max_length=2,
        choices=MODELO_CHOICES,
        help_text="Modelo de documento fiscal (55=NF-e, 65=NFC-e).",
    )

    serie = models.PositiveIntegerField(
        default=1,
        help_text="Série fiscal para este modelo de documento neste terminal.",
    )

    numero_atual = models.PositiveIntegerField(
        default=0,
        help_text="Último número utilizado. Próximo será numero_atual + 1.",
    )

    ativo = models.BooleanField(
        default=True,
        help_text="Se desativado, essa sequência não será mais usada.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Sequência de Documento Fiscal"
        verbose_name_plural = "Sequências de Documentos Fiscais"
        ordering = [
            "terminal__filial__razao_social",
            "terminal__identificador",
            "modelo",
            "serie",
        ]
        constraints = [
            # Não pode ter duas sequências iguais para o mesmo terminal/modelo/série
            models.UniqueConstraint(
                fields=["terminal", "modelo", "serie"],
                name="uniq_sequencia_terminal_modelo_serie",
            ),
        ]
        indexes = [
            models.Index(fields=["terminal"], name="idx_sequencia_terminal"),
            models.Index(fields=["modelo"], name="idx_sequencia_modelo"),
            models.Index(fields=["ativo"], name="idx_sequencia_ativo"),
        ]

    def __str__(self):
        return f"{self.terminal} - Mod {self.modelo} - Série {self.serie}"

    @property
    def proximo_numero(self) -> int:
        """Retorna em memória qual será o próximo número a emitir."""
        return self.numero_atual + 1
