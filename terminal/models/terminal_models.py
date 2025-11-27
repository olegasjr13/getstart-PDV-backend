from django.db import models
import uuid
from django.utils import timezone
from filial.models.filial_models import Filial

class Terminal(models.Model):
    """
    Representa um terminal de venda/PDV em uma filial.
    A numeração de documentos fiscais (séries e números) será
    controlada por terminal, através da model DocumentoFiscalSequencia.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        related_name="terminais",
        help_text="Filial à qual este terminal pertence.",
    )

    # Identificador lógico do terminal (ex.: PDV-01, CAIXA-01, etc.)
    identificador = models.CharField(
        max_length=40,
        help_text="Identificador único do terminal (ex.: PDV-01, CAIXA-01)."
    )

    abre_fecha_caixa = models.BooleanField(
        default=True,
        help_text="Define se o terminal tem permissão para abrir e fechar caixa."
    )

    permite_suprimento = models.BooleanField(
        default=True,
        help_text="Define se o terminal permite operação de suprimento."
    )
    permite_sangria = models.BooleanField(
        default=True,
        help_text="Define se o terminal permite operação de sangria."
    )

    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentual máximo de desconto permitido neste terminal.",
        blank=True,
        null=True,
    )

    desconto_automatico = models.BooleanField(
        default=False,
        help_text="Se marcado, aplica descontos automáticos conforme regras da filial." 
    )

    solicitar_senha_estorno = models.BooleanField(
        default=False,
        help_text=(
            "Se marcado, exige aprovação/senha de supervisor para estornar pagamentos "
            "no PDV. Se desmarcado, qualquer operador com acesso ao caixa pode estornar."
        ),
    )

    solicita_vendedor = models.BooleanField(
        default=False,
        help_text="Se marcado, o operador deve informar o vendedor para cada venda."
    )

    solicita_cpf_cliente = models.BooleanField(
        default=False,
        help_text="Se marcado, o operador deve informar o CPF do cliente para cada venda."
    )   
    solicita_identificacao_cliente = models.BooleanField(
        default=False,
        help_text="Se marcado, o operador deve informar a identificação do cliente para cada venda."
    )

    ativo = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indica se o terminal está ativo para uso."
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    # ---------------------------------------------------------------
    # Integração TEF
    # ---------------------------------------------------------------
    permite_tef = models.BooleanField(
        default=True,
        help_text="Indica se este terminal está habilitado para uso de TEF.",
    )
    tef_terminal_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text=(
            "Identificador do terminal no TEF (SITEF ou outro). "
            "Em muitas integrações, corresponde ao 'PDV' configurado no servidor TEF."
        ),
    )


    class Meta:
        verbose_name = "Terminal"
        verbose_name_plural = "Terminais"
        ordering = ["filial__nome_fantasia", "identificador"]
        constraints = [
            # Garante que não haverá dois terminais com o mesmo identificador na mesma filial
            models.UniqueConstraint(
                fields=["filial", "identificador"],
                name="uniq_terminal_filial_identificador"
            ),
        ]
        indexes = [
            models.Index(fields=["filial"], name="idx_terminal_filial"),
            models.Index(fields=["ativo"], name="idx_terminal_ativo"),
        ]

    def __str__(self):
        return f"{self.filial.nome_fantasia} - {self.identificador}"

