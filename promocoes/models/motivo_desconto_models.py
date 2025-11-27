# promocoes/models/motivo_desconto_models.py

import uuid
from django.db import models


class MotivoDesconto(models.Model):
    """
    Motivos cadastrados para concessão de desconto.
    Usado em descontos por item e/ou na venda inteira.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    codigo = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Código interno do motivo de desconto (ex.: PROMO10, QUEBRA, FIDELIDADE).",
    )
    descricao = models.CharField(
        max_length=255,
        help_text="Descrição legível do motivo de desconto."
    )

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "motivo_desconto"
        verbose_name = "Motivo de Desconto"
        verbose_name_plural = "Motivos de Desconto"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.descricao}"
