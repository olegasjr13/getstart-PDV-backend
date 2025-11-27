# metodoPagamento/models/filial_metodo_pagamento_models.py

import uuid

from django.db import models


class FilialMetodoPagamento(models.Model):
    """
    Relaciona quais métodos de pagamento estão disponíveis em cada Filial.

    - Multi-tenant: isolamento via schema (django-tenants).
    - unique_together(filial, metodo_pagamento) garante que não haverá
      duplicidade da mesma combinação em um tenant.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    filial = models.ForeignKey(
        "filial.Filial",
        on_delete=models.CASCADE,
        related_name="filiais_metodos_pagamento",
        help_text="Filial em que o método de pagamento está disponível.",
    )

    metodo_pagamento = models.ForeignKey(
        "metodoPagamento.MetodoPagamento",
        on_delete=models.CASCADE,
        related_name="metodos_pagamento_filiais",
        help_text="Método de pagamento disponível nesta filial.",
    )

    ativo = models.BooleanField(
        default=True,
        help_text="Indica se o método está ativo nesta filial.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "filial_metodo_pagamento"
        verbose_name = "Método de Pagamento por Filial"
        verbose_name_plural = "Métodos de Pagamento por Filial"
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "metodo_pagamento"],
                name="uniq_filial_met_pagamento",
            ),
        ]
        indexes = [
            models.Index(
                fields=["filial"],
                name="idx_filial_met_pgto_filial",
            ),
            models.Index(
                fields=["metodo_pagamento"],
                name="idx_filial_met_pgto_metodo",
            ),
            models.Index(
                fields=["ativo"],
                name="idx_filial_met_pgto_ativo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.filial.nome_fantasia} - {self.metodo_pagamento.descricao}"
