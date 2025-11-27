import uuid
from django.db import models

from commons.models.base_models import BaseModel



class Pais(BaseModel):
    """
    Tabela de países, com código NFe (cPais) e nome (xPais).
    Na NFe/NFC-e, o mais comum é cPais=1058 (Brasil).
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # cPais na NFe (ex.: 1058 para Brasil)
    codigo_nfe = models.CharField(
        max_length=4,
        unique=True,
        help_text="Código do país conforme tabela NFe (ex.: 1058 para Brasil).",
    )

    nome = models.CharField(
        max_length=60,
        unique=True,
        help_text="Nome do país (xPais na NFe).",
    )

    sigla2 = models.CharField(
        max_length=2,
        blank=True,
        help_text="Sigla ISO alpha-2 (ex.: BR).",
    )

    sigla3 = models.CharField(
        max_length=3,
        blank=True,
        help_text="Sigla ISO alpha-3 (ex.: BRA).",
    )

    class Meta:
        verbose_name = "País"
        verbose_name_plural = "Países"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["codigo_nfe"], name="idx_pais_codigo_nfe"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.codigo_nfe})"
