from django.db import models
import uuid

class Filial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True)
    nome_fantasia = models.CharField(max_length=120)
    uf = models.CharField(max_length=2)
    csc_id = models.CharField(max_length=50)
    csc_token = models.CharField(max_length=100)
    a1_pfx = models.BinaryField(null=True, blank=True)         # criptografado (fase 2)
    a1_expires_at = models.DateTimeField(null=True, blank=True)
    ambiente = models.CharField(max_length=12, default="homolog")  # homolog|producao
    created_at = models.DateTimeField(auto_now_add=True)
