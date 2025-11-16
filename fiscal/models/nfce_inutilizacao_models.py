import uuid
from django.db import models
from django.utils import timezone


class NfceInutilizacao(models.Model):
    """
    Registro de inutilização de faixa numérica de NFC-e.

    - Uma linha por faixa inutilizada (filial, série, faixa).
    - Idempotência via request_id.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    filial = models.ForeignKey(
        "filial.Filial",
        on_delete=models.PROTECT,
        related_name="nfce_inutilizacoes",
    )

    serie = models.PositiveIntegerField()
    numero_inicial = models.PositiveIntegerField()
    numero_final = models.PositiveIntegerField()

    # Identificador de idempotência da chamada que gerou a inutilização
    request_id = models.UUIDField(unique=True)

    # Protocolo retornado pela SEFAZ
    protocolo = models.CharField(max_length=64, blank=True, null=True)

    # Status interno da inutilização (ex.: "inutilizada", "erro")
    status = models.CharField(max_length=32, default="inutilizada")

    # Motivo enviado para SEFAZ
    motivo = models.TextField()

    # XML enviado e resposta da SEFAZ (quando aplicável)
    xml_envio = models.TextField(blank=True, null=True)
    xml_resposta = models.TextField(blank=True, null=True)

    raw_sefaz_response = models.JSONField(blank=True, null=True)

    ambiente = models.CharField(max_length=20, blank=True, null=True)
    uf = models.CharField(max_length=2, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nfce_inutilizacao"
        unique_together = (
            ("filial", "serie", "numero_inicial", "numero_final"),
        )
        indexes = [
            models.Index(fields=["filial", "serie", "numero_inicial", "numero_final"]),
            models.Index(fields=["request_id"]),
        ]

    def __str__(self):
        return (
            f"Inutilização NFC-e filial={self.filial_id} "
            f"serie={self.serie} faixa={self.numero_inicial}-{self.numero_final}"
        )
