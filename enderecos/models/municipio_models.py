import uuid
from django.db import models
from django.core.validators import MinLengthValidator

from commons.models.base_models import BaseModel
from enderecos.models.uf_models import UF

class Municipio(BaseModel):
    """
    Município conforme tabela IBGE/NFe.
    Na NFe:
      - cMun = código IBGE de 7 dígitos
      - xMun = nome do município
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    nome = models.CharField(
        max_length=60,
        help_text="Nome do município (xMun na NFe).",
    )

    uf = models.ForeignKey(
        UF,
        on_delete=models.PROTECT,
        related_name="municipios",
        help_text="UF do município.",
    )

    # Código IBGE do município (cMun na NFe)
    codigo_ibge = models.CharField(
        max_length=7,
        unique=True,
        validators=[MinLengthValidator(7)],
        help_text="Código IBGE do município (7 dígitos, cMun na NFe).",
    )

    # Opcionalmente códigos auxiliares (SIAFI, etc.)
    codigo_siafi = models.CharField(
        max_length=10,
        blank=True,
        help_text="Código SIAFI do município (se aplicável).",
    )

    class Meta:
        verbose_name = "Município"
        verbose_name_plural = "Municípios"
        ordering = ["uf__sigla", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["nome", "uf"],
                name="uniq_municipio_nome_uf"
            ),
        ]
        indexes = [
            models.Index(fields=["uf"], name="idx_municipio_uf"),
            models.Index(fields=["codigo_ibge"], name="idx_municipio_codigo_ibge"),
        ]

    def __str__(self):
        return f"{self.nome} / {self.uf.sigla}"

    @property
    def codigo_nfe(self) -> str:
        """
        Alias semântico para uso na NFe (cMun).
        """
        return self.codigo_ibge
