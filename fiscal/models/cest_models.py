# fiscal/models/cest_models.py
import uuid

from django.db import models

from fiscal.models.ncm_models import NCM

# -------------------------------------------------------------------
# CEST
# -------------------------------------------------------------------

class CEST(models.Model):
    """
    Código Especificador da Substituição Tributária (CEST).

    - Vinculado a 1 ou mais NCMs conforme legislação.
    - Cada CEST pode abranger vários NCM e um NCM pode ter múltiplos CEST,
      então a relação é ManyToMany.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        max_length=7,
        unique=True,
        db_index=True,
        help_text="Código CEST (7 dígitos).",
    )
    descricao = models.CharField(max_length=255)

    ncms = models.ManyToManyField(
        NCM,
        related_name="cests",
        blank=True,
        help_text="Lista de NCMs cobertos por este CEST.",
    )

    vigencia_inicio = models.DateField(blank=True, null=True)
    vigencia_fim = models.DateField(blank=True, null=True)

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CEST"
        verbose_name_plural = "CESTs"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.descricao}"
    
