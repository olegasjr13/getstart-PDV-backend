import uuid
from django.db import models
from django.utils import timezone

class NfceNumeroReserva(models.Model):
    """
    Reserva de numeração NFC-e por terminal/serie, idempotente via request_id (único por tenant).
    Em tenant schema (TENANT_APPS).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Chaves de contexto (não FK para evitar lock cruzado; guardar apenas UUID/valor)
    terminal_id = models.UUIDField()      # terminal.models.terminal_models.Terminal.id
    filial_id   = models.UUIDField()      # filial.models.filial_models.Filial.id

    serie      = models.PositiveIntegerField()
    numero     = models.PositiveIntegerField()  # número reservado
    request_id = models.UUIDField(unique=True)  # idempotência por request_id (único no schema)

    reserved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "nfce_numero_reserva"
        indexes = [
            models.Index(fields=["terminal_id", "serie"]),
            models.Index(fields=["filial_id"]),
        ]

    def __str__(self):
        return f"Reserva NFC-e: term={self.terminal_id} serie={self.serie} num={self.numero}"
