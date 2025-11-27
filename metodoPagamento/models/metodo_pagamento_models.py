# metodoPagamento/models/metodo_pagamento_models.py
import uuid

from django.db import models
from django.core.exceptions import ValidationError


# -------------------------------------------------------------------
# METODO DE PAGAMENTO
# -------------------------------------------------------------------

class MetodoPagamentoTipo(models.TextChoices):
    DINHEIRO = "DIN", "Dinheiro"
    PIX = "PIX", "PIX"
    CREDITO = "CRC", "Cartão de Crédito"
    DEBITO = "CRD", "Cartão de Débito"
    VOUCHER = "VCH", "Voucher / Refeição"
    OUTRO = "OUT", "Outros"


# Tabela tPag NFe/NFC-e (forma de pagamento) - principais códigos
CODIGOS_FISCAIS_VALIDOS = {
    "01",  # Dinheiro
    "02",  # Cheque
    "03",  # Cartão de Crédito
    "04",  # Cartão de Débito
    "05",  # Crédito Loja
    "10",  # Vale Alimentação
    "11",  # Vale Refeição
    "12",  # Vale Presente
    "13",  # Vale Combustível
    "15",  # Boleto Bancário
    "16",  # Depósito Bancário
    "17",  # Pagamento Instantâneo (PIX)
    "18",  # Transferência Bancária, Carteira Digital
    "19",  # Programas de Fidelidade, Cashback etc.
    "90",  # Sem Pagamento
    "99",  # Outros
}

# Mapeamento recomendado entre tipo lógico e códigos fiscais.
# Não é uma tabela oficial, mas uma coerência forte para evitar erro humano.
TIPO_X_CODIGOS_FISCAIS_RECOMENDADOS: dict[str, set[str]] = {
    MetodoPagamentoTipo.DINHEIRO: {"01"},
    MetodoPagamentoTipo.PIX: {"17"},
    MetodoPagamentoTipo.CREDITO: {"03", "05"},
    MetodoPagamentoTipo.DEBITO: {"04"},
    MetodoPagamentoTipo.VOUCHER: {"10", "11", "12", "13"},
    # OUTRO: aceita qualquer um da tabela, então não restringimos.
}


class MetodoPagamento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    codigo = models.CharField(
        max_length=7,
        unique=True,
        db_index=True,
        help_text="Código interno do método de pagamento (até 7 caracteres).",
    )
    tipo = models.CharField(
        max_length=3,
        choices=MetodoPagamentoTipo.choices,
        help_text="Tipo lógico do método (dinheiro, PIX, crédito, débito, etc).",
    )

    descricao = models.CharField(max_length=255)
    utiliza_tef = models.BooleanField(
        default=False,
        help_text="Indica se este método utiliza TEF/SITEF.",
    )

    # Mapeamentos externos
    codigo_fiscal = models.CharField(
        max_length=2,
        help_text="Código da forma de pagamento no XML (ex: '01'=Dinheiro, '03'=Cartão de Crédito).",
    )
    codigo_tef = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Código equivalente no TEF/SITEF, se aplicável.",
    )
    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentual de desconto automático ao usar este método.",
    )
    permite_parcelamento = models.BooleanField(default=False)
    max_parcelas = models.PositiveSmallIntegerField(default=1)
    valor_minimo_parcela = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor mínimo permitido por parcela, se parcelamento for permitido.",
    )

    permite_troco = models.BooleanField(
        default=True,
        help_text="Indica se esse método permite troco (normalmente só dinheiro).",
    )
    ordem_exibicao = models.PositiveSmallIntegerField(default=0)

    permite_desconto = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "metodo_pagamento"
        verbose_name = "Método de Pagamento"
        verbose_name_plural = "Métodos de Pagamento"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.descricao}"

    # -------------------------------------------------------------------
    # Regras de negócio / validações "conformes normas"
    # -------------------------------------------------------------------
    def clean(self):
        errors = {}

        # --- codigo_fiscal: 2 dígitos numéricos e dentro da tabela tPag ---
        if not self.codigo_fiscal or not self.codigo_fiscal.isdigit():
            errors["codigo_fiscal"] = (
                "O código fiscal deve conter apenas dígitos numéricos "
                "conforme tabela tPag da NFe/NFC-e."
            )
        elif len(self.codigo_fiscal) != 2:
            errors["codigo_fiscal"] = (
                "O código fiscal deve ter exatamente 2 dígitos (ex.: '01', '03', '17')."
            )
        elif self.codigo_fiscal not in CODIGOS_FISCAIS_VALIDOS:
            errors["codigo_fiscal"] = (
                f"Código fiscal '{self.codigo_fiscal}' não é válido para formas de "
                "pagamento da NFe/NFC-e (tabela tPag)."
            )

        # --- Compatibilidade recomendada entre tipo e código_fiscal ---
        # Só validamos se existir um conjunto recomendado para o tipo.
        codigos_recomendados = TIPO_X_CODIGOS_FISCAIS_RECOMENDADOS.get(self.tipo)
        if codigos_recomendados and self.codigo_fiscal not in codigos_recomendados:
            errors["codigo_fiscal"] = (
                f"Código fiscal '{self.codigo_fiscal}' não é compatível com o tipo "
                f"'{self.get_tipo_display()}'. Utilize um dos códigos: "
                f"{', '.join(sorted(codigos_recomendados))}."
            )

        # --- Desconto automático: se informado, 0 <= x <= 100 e requer permite_desconto ---
        if self.desconto_automatico_percentual is not None:
            if self.desconto_automatico_percentual < 0 or self.desconto_automatico_percentual > 100:
                errors["desconto_automatico_percentual"] = (
                    "O desconto automático deve estar entre 0% e 100%."
                )
            if not self.permite_desconto:
                errors["desconto_automatico_percentual"] = (
                    "Não é possível definir desconto automático se 'permite_desconto' "
                    "estiver desativado."
                )

        # --- Regras de parcelamento ---
        if not self.permite_parcelamento:
            # Sem parcelamento: max_parcelas deve ser 1 e valor_minimo_parcela vazio
            if self.max_parcelas != 1:
                errors["max_parcelas"] = (
                    "Se o parcelamento não é permitido, 'max_parcelas' deve ser igual a 1."
                )
            if self.valor_minimo_parcela is not None:
                errors["valor_minimo_parcela"] = (
                    "Se o parcelamento não é permitido, 'valor_minimo_parcela' deve ficar vazio."
                )
        else:
            # Com parcelamento: max_parcelas >= 2
            if self.max_parcelas < 2:
                errors["max_parcelas"] = (
                    "Se o parcelamento é permitido, 'max_parcelas' deve ser no mínimo 2."
                )
            if self.valor_minimo_parcela is not None and self.valor_minimo_parcela <= 0:
                errors["valor_minimo_parcela"] = (
                    "O valor mínimo por parcela, quando informado, deve ser maior que zero."
                )

        # --- Troco: por regra de negócio, normalmente só DINHEIRO permite troco ---
        # Não vou bloquear 100% (há casos especiais), mas se quiser, podemos endurecer:
            if self.permite_troco and self.tipo != MetodoPagamentoTipo.DINHEIRO:
                errors["permite_troco"] = (
                 "Por padrão, apenas o tipo 'Dinheiro' deve permitir troco."
             )

        if errors:
            raise ValidationError(errors)
