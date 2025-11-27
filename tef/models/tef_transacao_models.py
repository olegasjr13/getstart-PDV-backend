import uuid

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q

from tef.models.tef_models import TefProvider

class TefTransacaoStatus(models.TextChoices):
    APROVADA = "APROVADA", "Aprovada"
    NEGADA = "NEGADA", "Negada"
    ERRO_COMUNICACAO = "ERRO_COMUNICACAO", "Erro de comunicação"
    PENDENTE = "PENDENTE", "Pendente"


class TefTransacao(models.Model):
    """
    Representa uma transação TEF vinculada a um pagamento de venda.

    - 1:1 com VendaPagamento (um pagamento TEF tem uma transação principal).
    - Guarda dados necessários para reimpressão e conciliação.
    - NÃO guarda dados sensíveis de cartão (apenas mascarado).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    pagamento = models.OneToOneField(
        "vendas.VendaPagamento",
        on_delete=models.CASCADE,
        related_name="tef_transacao",
        help_text="Pagamento de venda associado a esta transação TEF.",
    )

    provider = models.CharField(
        max_length=20,
        choices=TefProvider.choices,
        default=TefProvider.SITEF,
        help_text="Provider TEF utilizado nesta transação.",
    )

    status = models.CharField(
        max_length=20,
        choices=TefTransacaoStatus.choices,
        help_text="Status final da transação TEF.",
    )

    nsu_sitef = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="NSU/identificador da transação no TEF (ex.: SITEF).",
    )   

    nsu_host = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="NSU/identificador da transação no host/adquirente.",
    )

    codigo_autorizacao = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Código de autorização devolvido pela adquirente.",
    )

    bandeira = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Bandeira do cartão (ex.: Visa, MasterCard).",
    )

    modalidade = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Modalidade (Crédito, Débito, Voucher etc).",
    )

    parcelas = models.PositiveSmallIntegerField(
        default=1,
        help_text="Quantidade de parcelas (1=à vista).",
    )

    valor_transacao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Valor autorizado na transação TEF.",
        blank=True,
        null=True,
    )

    pan_mascarado = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Número do cartão mascarado (ex.: **** **** **** 1234).",
    )

    codigo_retorno = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        help_text="Código de retorno da transação TEF.",
    )

    mensagem_retorno = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Mensagem de retorno resumida.",
    )

    comprovante_cliente = models.TextField(
        blank=True,
        null=True,
        help_text="Texto do comprovante do cliente.",
    )

    comprovante_estabelecimento = models.TextField(
        blank=True,
        null=True,
        help_text="Texto do comprovante do estabelecimento.",
    )

    raw_data = models.JSONField(
        blank=True,
        null=True,
        help_text="Payload bruto retornado pelo TEF (sem dados sensíveis).",
    )
    filial= models.ForeignKey(
        "filial.Filial",
        on_delete=models.PROTECT,
        help_text="Filial onde a transação foi realizada.",
        blank=True,
        null=True,
    )   
    venda = models.ForeignKey(
        "vendas.Venda",
        on_delete=models.PROTECT,
        help_text="Venda associada a esta transação TEF.",
        blank=True,
        null=True,
    )   
    terminal = models.ForeignKey(
        "terminal.Terminal",
        on_delete=models.PROTECT,
        help_text="Terminal onde a transação foi realizada.",
        blank=True,
        null=True,
    )
    raw_request = models.TextField(
        blank=True,
        null=True,
        help_text="Dados brutos enviados na requisição TEF.",
    )
    raw_response = models.TextField(
        blank=True,
        null=True,        
        help_text="Dados brutos retornados pela requisição TEF.",    
    )
    valor_confirmado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Valor confirmado na transação TEF.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tef_transacao"
        verbose_name = "Transação TEF"
        verbose_name_plural = "Transações TEF"
        indexes = [
            models.Index(fields=["provider"], name="idx_teftrans_provider"),
            models.Index(fields=["status"], name="idx_teftrans_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["nsu_sitef"],
                condition=Q(nsu_sitef__isnull=False),
                name="uq_teftransacao_nsu_sitef_not_null",
            ),
            models.UniqueConstraint(
                fields=["nsu_host"],
                condition=Q(nsu_host__isnull=False),
                name="uq_teftransacao_nsu_host_not_null",
            ),
        ]

    def __str__(self) -> str:
        return f"TEF {self.id} - Pagamento {self.pagamento_id} - {self.status}"

    def clean(self):
        errors = {}
        if self.valor_transacao <= 0:
            errors["valor_transacao"] = "O valor da transação TEF deve ser maior que zero."
        if self.parcelas < 1:
            errors["parcelas"] = "Quantidade de parcelas deve ser pelo menos 1."
        if errors:
            raise ValidationError(errors)
        
    @property
    def eh_sucesso(self) -> bool:
        return self.status == TefTransacaoStatus.APROVADA

    @property
    def eh_negada(self) -> bool:
        return self.status == TefTransacaoStatus.NEGADA
