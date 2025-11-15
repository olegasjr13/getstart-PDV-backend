# fiscal/models/pre_emissao_models.py
from django.db import models
from uuid import uuid4

class NfcePreEmissao(models.Model):
    """
    Registro de pré-emissão antes da comunicação com a SEFAZ (S12).
    Cada pré-emissão está vinculada a uma reserva de número (idempotência).
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    filial_id = models.UUIDField()
    terminal_id = models.UUIDField()

    numero = models.BigIntegerField()
    serie = models.IntegerField()

    request_id = models.UUIDField(unique=True)

    payload = models.JSONField()  # dados completos da NFC-e enviados pelo PDV

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "nfce_pre_emissao"
        unique_together = ("filial_id", "terminal_id", "serie", "numero")

    def __str__(self):
        return f"Pré-Emissão NFC-e {self.numero}/{self.serie}"
