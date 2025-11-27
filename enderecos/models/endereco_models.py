import uuid
from django.db import models
from django.core.validators import MinLengthValidator

from commons.models.base_models import BaseModel
from enderecos.models.logradouro_models import Logradouro
from enderecos.models.municipio_models import Municipio
from enderecos.models.pais_models import Pais

class Endereco(BaseModel):
    """
    Endereço completo utilizado em NF-e/NFC-e.

    A NFe exige:
      - xLgr (logradouro)
      - nro  (número)
      - xCpl (complemento - opcional)
      - xBairro
      - cMun / xMun
      - UF
      - CEP
      - cPais / xPais
    Tudo isso pode ser derivado dos relacionamentos abaixo.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    logradouro = models.ForeignKey(
        Logradouro,
        on_delete=models.PROTECT,
        related_name="enderecos",
        help_text="Logradouro (xLgr) do endereço.",
    )

    numero = models.CharField(
        max_length=10,
        help_text="Número do endereço (nro). Use 'S/N' se sem número.",
    )

    complemento = models.CharField(
        max_length=60,
        blank=True,
        help_text="Complemento (xCpl), se houver.",
    )

    referencia = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ponto de referência (uso interno, não vai na NF-e).",
    )

    # CEP pode ser herdado do logradouro como padrão, mas permitimos overwrite
    cep = models.CharField(
        max_length=8,
        validators=[MinLengthValidator(8)],
        help_text="CEP completo (somente números).",
    )

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ["logradouro__bairro__municipio__nome", "logradouro__nome", "numero"]
        indexes = [
            models.Index(fields=["cep"], name="idx_endereco_cep"),
        ]

    def __str__(self):
        return f"{self.logradouro} , {self.numero}"

    #
    # Propriedades auxiliares para uso direto na NFe/NFC-e
    #

    @property
    def xLgr(self) -> str:
        """Nome completo do logradouro para xLgr."""
        return f"{self.logradouro.get_tipo_display()} {self.logradouro.nome}"

    @property
    def xBairro(self) -> str:
        return self.logradouro.bairro.nome

    @property
    def municipio(self) -> Municipio:
        return self.logradouro.bairro.municipio

    @property
    def xMun(self) -> str:
        return self.municipio.nome

    @property
    def cMun(self) -> str:
        return self.municipio.codigo_ibge

    @property
    def uf(self) -> str:
        return self.municipio.uf.sigla

    @property
    def pais(self) -> Pais:
        return self.municipio.uf.pais

    @property
    def cPais(self) -> str:
        return self.pais.codigo_nfe

    @property
    def xPais(self) -> str:
        return self.pais.nome
