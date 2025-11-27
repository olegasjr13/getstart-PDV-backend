import uuid
from django.db import models
from django.core.validators import MinLengthValidator

from enderecos.models.endereco_models import Endereco
from django.core.validators import MinLengthValidator, MinValueValidator, MaxValueValidator



class Filial(models.Model):
    """
    Filial emitente (cadastro básico).
    Identidade da empresa/filial, sem detalhes fiscais complexos.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    razao_social = models.CharField(
        max_length=120,
        help_text="Razão social da empresa emitente (xNome)."
    )

    nome_fantasia = models.CharField(
        max_length=120,
        help_text="Nome fantasia da filial (xFant).",
    )

    cnpj = models.CharField(
        max_length=14,
        unique=True,
        validators=[MinLengthValidator(14)],
        db_index=True,
        help_text="CNPJ da filial (somente números, 14 dígitos).",
    )

    ie = models.CharField(
        max_length=14,
        validators=[MinLengthValidator(2)],
        help_text="Inscrição Estadual da filial (IE).",
        default="ISENTO",
    )
    im = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Inscrição Municipal da filial (IM).",
    )

    endereco = models.ForeignKey(
        Endereco,
        on_delete=models.PROTECT,
        related_name="filiais",
        help_text="Endereço fiscal da filial (enderEmit na NFe)."
    )
    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentual máximo de desconto permitido para esta filial.",
        blank=True,
        null=True,
    )

    ativo = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indica se a filial está ativa para emissão.",
    )

    casas_decimais_preco_display = models.PositiveSmallIntegerField(
        default=2,
        choices=(
            (2, "2 casas decimais (padrão; moeda)"),
            (3, "3 casas decimais"),
            (4, "4 casas decimais"),
        ),
        validators=[MinValueValidator(2), MaxValueValidator(4)],
        help_text=(
            "Quantidade de casas decimais para exibição de preços no PDV. "
            "O backend continuará calculando internamente com maior precisão; "
            "esta configuração afeta apenas apresentação e arredondamento em tela."
        ),
    )


    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Filial"
        verbose_name_plural = "Filiais"
        ordering = ["razao_social"]
        indexes = [
            models.Index(fields=["cnpj"], name="idx_filial_cnpj"),
            models.Index(fields=["ativo"], name="idx_filial_ativo"),
        ]

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    # Atalhos úteis (repassam do endereço)

    @property
    def uf(self) -> str:
        return self.endereco.uf

    @property
    def cMun(self) -> str:
        return self.endereco.cMun

    @property
    def xMun(self) -> str:
        return self.endereco.xMun

    @property
    def cep(self) -> str:
        return self.endereco.cep

    @property
    def cPais(self) -> str:
        return self.endereco.cPais

    @property
    def xPais(self) -> str:
        return self.endereco.xPais
    
    def get_casas_decimais_preco_display(self) -> int:
        """
        Retorna o número de casas decimais configurado para exibição de preços.
        Garantimos um fallback seguro para 2 casas, se houver algum problema.
        """
        valor = self.casas_decimais_preco_display or 2
        if valor < 2:
            return 2
        if valor > 4:
            return 4
        return valor

