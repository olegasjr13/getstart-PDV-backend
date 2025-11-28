# caixa/models.py

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal


class Caixa(models.Model):
    """
    Representa a movimentação de caixa de um TERMINAL em um período contínuo.

    Regras principais:
    - Apenas 1 Caixa com status ABERTO por Terminal.
    - Pode haver um ou mais operadores atuando, mas o responsável
      pela abertura/fechamento fica registrado.
    """

    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        FECHADO = "FECHADO", "Fechado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        related_name="caixas",
    )
    terminal = models.ForeignKey(
        Terminal,
        on_delete=models.PROTECT,
        related_name="caixas",
    )

    operador_abertura = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="caixas_abertos",
    )
    operador_fechamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="caixas_fechados",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABERTO,
    )

    saldo_inicial = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    saldo_final_calculado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    saldo_final_informado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    diferenca = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    aberto_em = models.DateTimeField(default=timezone.now)
    fechado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "caixa"
        indexes = [
            models.Index(fields=["filial", "terminal", "status"]),
        ]

    def __str__(self) -> str:
        return f"Caixa {self.id} - Terminal {self.terminal_id} - {self.status}"


class Suprimento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    caixa = models.ForeignKey(
        Caixa,
        on_delete=models.PROTECT,
        related_name="suprimentos",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    motivo = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "caixa_suprimento"

    def __str__(self) -> str:
        return f"Suprimento {self.valor} - Caixa {self.caixa_id}"


class Sangria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    caixa = models.ForeignKey(
        Caixa,
        on_delete=models.PROTECT,
        related_name="sangrias",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    motivo = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "caixa_sangria"

    def __str__(self) -> str:
        return f"Sangria {self.valor} - Caixa {self.caixa_id}"
