import uuid
from django.db import models

from commons.models.base_models import BaseModel
from enderecos.models.municipio_models import Municipio

class Bairro(BaseModel):
    """
    Bairro dentro de um município.
    Usado para compor o endereço da NF-e (xBairro).
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    nome = models.CharField(
        max_length=60,
        help_text="Nome do bairro (xBairro).",
    )

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="bairros",
        help_text="Município ao qual o bairro pertence.",
    )

    class Meta:
        verbose_name = "Bairro"
        verbose_name_plural = "Bairros"
        ordering = ["municipio__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["nome", "municipio"],
                name="uniq_bairro_nome_municipio"
            ),
        ]
        indexes = [
            models.Index(fields=["municipio"], name="idx_bairro_municipio"),
        ]

    def __str__(self):
        return f"{self.nome} - {self.municipio}"
