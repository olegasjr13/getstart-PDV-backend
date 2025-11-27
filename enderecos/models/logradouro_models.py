import uuid
from django.db import models

from django.core.validators import MinLengthValidator
from commons.models.base_models import BaseModel
from enderecos.models.bairro_models import Bairro
from enderecos.models.municipio_models import Municipio
from enderecos.models.uf_models import UF

class Logradouro(BaseModel):
    """
    Logradouro (rua, avenida, etc.) dentro de um município/bairro.
    Na NFe, é usado em xLgr.
    """
    TIPO_RUA = "RUA"
    TIPO_AVENIDA = "AV"
    TIPO_RODOVIA = "ROD"
    TIPO_OUTROS = "OUTROS"

    TIPO_CHOICES = (
        (TIPO_RUA, "Rua"),
        (TIPO_AVENIDA, "Avenida"),
        (TIPO_RODOVIA, "Rodovia"),
        (TIPO_OUTROS, "Outros"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default=TIPO_RUA,
        help_text="Tipo de logradouro (Rua, Avenida, Rodovia, etc.).",
    )

    nome = models.CharField(
        max_length=80,
        help_text="Nome do logradouro (sem o tipo). Ex.: 'Paulista'.",
    )

    bairro = models.ForeignKey(
        Bairro,
        on_delete=models.PROTECT,
        related_name="logradouros",
        help_text="Bairro em que este logradouro se encontra.",
    )

    # CEP geralmente é por logradouro/faixa, mas mantemos um CEP base
    cep = models.CharField(
        max_length=8,
        validators=[MinLengthValidator(8)],
        help_text="CEP base do logradouro (somente números).",
    )

    class Meta:
        verbose_name = "Logradouro"
        verbose_name_plural = "Logradouros"
        ordering = ["bairro__municipio__nome", "bairro__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo", "nome", "bairro"],
                name="uniq_logradouro_tipo_nome_bairro"
            ),
        ]
        indexes = [
            models.Index(fields=["bairro"], name="idx_logradouro_bairro"),
            models.Index(fields=["cep"], name="idx_logradouro_cep"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.nome} - {self.bairro}"

    @property
    def municipio(self) -> Municipio:
        return self.bairro.municipio

    @property
    def uf(self) -> UF:
        return self.bairro.municipio.uf
