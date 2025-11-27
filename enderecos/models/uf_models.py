import uuid
from django.db import models
from django.core.validators import MinLengthValidator

from enderecos.models.pais_models import Pais

class UF(models.Model):
    """
    Unidade da Federação (Estado), conforme tabela NFe/IBGE.
    Ex.: sigla=SP, codigo_ibge=35
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    
    sigla = models.CharField(
        max_length=2,
        unique=True,
        help_text="Sigla da UF (ex.: SP, RJ, MG).",
    )

    nome = models.CharField(
        max_length=60,
        unique=True,
        help_text="Nome da UF (ex.: São Paulo).",
    )

    # Código IBGE da UF (2 dígitos, mas em geral tratado como inteiro/char)
    codigo_ibge = models.CharField(
        max_length=2,
        unique=True,
        validators=[MinLengthValidator(2)],
        help_text="Código IBGE da UF (2 dígitos).",
    )

    pais = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        related_name="ufs",
        help_text="País ao qual esta UF pertence (normalmente Brasil).",
    )

    class Meta:
        verbose_name = "UF"
        verbose_name_plural = "UFs"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["codigo_ibge"], name="idx_uf_codigo_ibge"),
        ]

    def __str__(self):
        return f"{self.sigla} - {self.nome}"
