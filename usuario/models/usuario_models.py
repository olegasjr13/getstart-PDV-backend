from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # username/email padrões do Django
    pin_hash = models.CharField(max_length=256, null=True, blank=True)
    perfil = models.CharField(
        max_length=20,
        choices=[("OPERADOR","OPERADOR"),("SUPERVISOR","SUPERVISOR"),
                 ("GERENTE","GERENTE"),("ADMIN","ADMIN")],
        default="OPERADOR"
    )

class UserFilial(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filial_id = models.UUIDField()
    class Meta:
        unique_together = ("user","filial_id")
