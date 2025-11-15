from django.db import models
import uuid

class Terminal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filial_id = models.UUIDField()
    identificador = models.CharField(max_length=40, unique=True)  # enrolamento QR
    serie = models.IntegerField(default=1)
    numero_atual = models.IntegerField(default=0)
    permite_suprimento = models.BooleanField(default=True)
    permite_sangria = models.BooleanField(default=True)
