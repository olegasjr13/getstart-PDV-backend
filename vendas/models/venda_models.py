# vendas/models/venda_models.py

import uuid
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from caixa.models.caixa_models import Caixa
from commons.models.base_models import BaseModel
from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User

def _somente_digitos(valor: str) -> str:
    return "".join(ch for ch in valor if ch.isdigit())


def _cpf_valido(cpf: str) -> bool:
    """
    Validação simples de CPF:
    - Remove caracteres não numéricos
    - Confere se tem 11 dígitos
    - Rejeita sequências repetidas (000..., 111..., etc.)
    - Valida dígitos verificadores
    """
    cpf = _somente_digitos(cpf or "")
    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    def calc_dv(digs: str) -> str:
        soma = 0
        peso = len(digs) + 1
        for c in digs:
            soma += int(c) * peso
            peso -= 1
        resto = soma % 11
        if resto < 2:
            return "0"
        return str(11 - resto)

    dv1 = calc_dv(cpf[:9])
    dv2 = calc_dv(cpf[:9] + dv1)
    return cpf[-2:] == dv1 + dv2


class VendaStatus(models.TextChoices):
    ABERTA = "ABERTA", "Aberta (montando carrinho)"
    AGUARDANDO_PAGAMENTO = "AG_PAG", "Aguardando pagamento"
    PAGAMENTO_EM_PROCESSAMENTO = "PG_PROC", "Pagamento em processamento"
    PAGAMENTO_CONFIRMADO = "PG_OK", "Pagamento confirmado"
    AGUARDANDO_EMISSAO_FISCAL = "AG_DOC", "Aguardando emissão fiscal"
    ERRO_FISCAL = "ERRO_FISCAL", "Erro fiscal"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CANCELADA = "CANCELADA", "Cancelada"



class TipoVenda(models.TextChoices):
    VENDA_NORMAL = "VENDA", "Venda normal (com documento fiscal)"
    ORCAMENTO = "ORCAMENTO", "Orçamento / Pré-venda (sem emissão fiscal)"
    PEDIDO_INTERNO = "INTERNO", "Pedido interno / consumo próprio"


class TipoDocumentoFiscal(models.TextChoices):
    NFCE = "NFCE", "NFC-e"
    NFE = "NFE", "NF-e"
    NENHUM = "NENHUM", "Nenhum (orcamento/pedido interno)"


class Venda(BaseModel):
    """
    Representa uma venda/pedido no PDV.

    Pilares:
    - Multi-tenant via schema (django-tenants).
    - Ligada a uma Filial e um Terminal específicos.
    - Um usuário operador responsável pela abertura/fechamento.
    - Pode ter múltiplos itens (VendaItem).
    - Pode ter múltiplos pagamentos (VendaPagamento).
    - Documento fiscal pode ser NFC-e, NFe ou nenhum (orcamento/pedido interno).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        related_name="vendas",
        help_text="Filial em que a venda foi realizada.",
    )

    terminal = models.ForeignKey(
        Terminal,
        on_delete=models.PROTECT,
        related_name="vendas",
        help_text="Terminal (PDV) responsável pela venda.",
    )

    operador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="vendas_operadas",
        help_text="Usuário operador que abriu/fechou a venda.",
    )

    caixa = models.ForeignKey(
        Caixa,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendas",
        help_text="Caixa em que a venda foi realizada.",
    )

    tipo_venda = models.CharField(
        max_length=20,
        choices=TipoVenda.choices,
        default=TipoVenda.VENDA_NORMAL,
        help_text="Tipo de venda (normal, orçamento, pedido interno).",
    )

    documento_fiscal_tipo = models.CharField(
        max_length=10,
        choices=TipoDocumentoFiscal.choices,
        default=TipoDocumentoFiscal.NFCE,
        help_text="Tipo de documento fiscal associado (NFC-e, NF-e ou nenhum).",
    )

    status = models.CharField(
        max_length=20,
        choices=VendaStatus.choices,
        default=VendaStatus.ABERTA,
        help_text="Estado atual da venda no fluxo de negócio.",
    )

    cpf_na_nota = models.CharField(
        max_length=14,
        null=True,
        blank=True,
        help_text=(
            "CPF do consumidor para impressão na NFC-e/NF-e. "
            "Pode ser informado com ou sem máscara."
        ),
    )

    identificacao_cliente = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=(
            "Identificação adicional do cliente (nome, código, etc.) "
            "para impressão na NFC-e/NF-e."
        ),
    )

    vendedor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="vendas_vendidas",
        null=True,
        blank=True,
        help_text="Vendedor associado à venda, se aplicável.",
    )


    # Totais financeiros básicos
    total_bruto = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_desconto = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_liquido = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_pago = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_troco = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # vendas/models/venda_models.py (dentro de Venda)

    percentual_desconto_global = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Percentual de desconto global aplicado sobre o total da venda "
            "antes da distribuição por itens. Opcional; pode ser 0/NULL caso "
            "apenas descontos por item sejam usados."
        ),
    )

    motivo_desconto_global = models.ForeignKey(
        "promocoes.MotivoDesconto",
        on_delete=models.PROTECT,
        related_name="vendas_com_desconto_global",
        null=True,
        blank=True,
        help_text="Motivo do desconto global da venda.",
    )

    desconto_global_aprovado_por = models.ForeignKey(
        "usuario.User",
        on_delete=models.PROTECT,
        related_name="vendas_com_desconto_aprovado",
        null=True,
        blank=True,
        help_text=(
            "Usuário que aprovou o desconto global, quando excedeu o limite "
            "do operador."
        ),
    )


    # Idempotência / rastreio
    request_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text=(
            "Identificador único da requisição de venda (para evitar "
            "duplicidades em cenários de queda de conexão)."
        ),
    )

    codigo_erro_fiscal = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Último código de erro fiscal retornado pela SEFAZ / API fiscal.",
    )
    mensagem_erro_fiscal = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Última mensagem de erro fiscal resumida.",
    )

    nfce_documento = models.ForeignKey(
        "fiscal.NfceDocumento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendas_origem",
        help_text="Documento NFC-e gerado para esta venda, quando aplicável.",
    )

    observacoes = models.TextField(blank=True, null=True)

    data_abertura = models.DateTimeField(auto_now_add=True)
    data_fechamento = models.DateTimeField(blank=True, null=True)

    
    class Meta:
        db_table = "venda"
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        indexes = [
            models.Index(fields=["filial"], name="idx_venda_filial"),
            models.Index(fields=["terminal"], name="idx_venda_terminal"),
            models.Index(fields=["status"], name="idx_venda_status"),
            models.Index(fields=["request_id"], name="idx_venda_request_id"),
        ]

    def __str__(self) -> str:
        return f"Venda {self.id} - Filial {self.filial_id} - Terminal {self.terminal_id}"

    # ------------------------------------------------------------------
    # Regras básicas de consistência
    # ------------------------------------------------------------------
    def clean(self):
        errors = {}

        # Regras já existentes
        if self.tipo_venda in {TipoVenda.ORCAMENTO, TipoVenda.PEDIDO_INTERNO}:
            if self.documento_fiscal_tipo != TipoDocumentoFiscal.NENHUM:
                errors["documento_fiscal_tipo"] = (
                    "Para orçamentos/pedidos internos, o tipo de documento "
                    "fiscal deve ser 'NENHUM'."
                )

        if (
            self.tipo_venda == TipoVenda.VENDA_NORMAL
            and self.documento_fiscal_tipo == TipoDocumentoFiscal.NENHUM
        ):
            errors["documento_fiscal_tipo"] = (
                "Vendas normais devem estar configuradas para emitir NFC-e ou NF-e."
            )

        # Totais não negativos
        for campo in ["total_bruto", "total_desconto", "total_liquido", "total_pago", "total_troco"]:
            valor = getattr(self, campo, None)
            if valor is not None and valor < 0:
                errors[campo] = "O campo não pode ser negativo."

        # Coerência entre bruto / desconto / líquido (opcional, mas forte)
        if (
            self.total_bruto is not None
            and self.total_desconto is not None
            and self.total_liquido is not None
        ):
            if self.total_desconto > self.total_bruto:
                errors["total_desconto"] = (
                    "Total de desconto não pode ser maior que o total bruto."
                )

            esperado = self.total_bruto - self.total_desconto
            if esperado != self.total_liquido:
                errors["total_liquido"] = (
                    "Total líquido deve ser igual ao total_bruto - total_desconto."
                )
        # Validação de CPF na nota (se informado)
        if self.cpf_na_nota:
            cpf_raw = str(self.cpf_na_nota).strip()
            if not _cpf_valido(cpf_raw):
                errors["cpf_na_nota"] = "CPF informado é inválido."
            else:
                # Normaliza a versão armazenada para somente dígitos
                self.cpf_na_nota = _somente_digitos(cpf_raw)

        if errors:
            raise ValidationError(errors)
  
    # ------------------------------------------------------------------
    # Helpers de status / fluxo
    # ------------------------------------------------------------------
    def esta_aberta_para_pagamento(self) -> bool:
        """
        Indica se a venda está em um status que permite registrar pagamentos.
        """
        return self.status in {
            VendaStatus.ABERTA,
            VendaStatus.AGUARDANDO_PAGAMENTO,
        }

    @property
    def saldo_a_pagar(self) -> Decimal:
        """
        Saldo efetivo a pagar considerando:
        - total_liquido (valor final da venda)
        - total_pago (somatório dos pagamentos efetivos)
        - total_troco (devolvido ao cliente)

        Fórmula:
            saldo = total_liquido - total_pago + total_troco
        """
        from decimal import Decimal as D

        tl = self.total_liquido or D("0.00")
        tp = self.total_pago or D("0.00")
        tt = self.total_troco or D("0.00")
        return tl - tp + tt

    # Helpers simples para uso posterior
    @property
    def eh_finalizada(self) -> bool:
        return self.status == VendaStatus.FINALIZADA

    @property
    def possui_erro_fiscal(self) -> bool:
        return self.status == VendaStatus.ERRO_FISCAL




