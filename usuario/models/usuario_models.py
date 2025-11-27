from django.contrib.auth.models import AbstractUser
from django.db import models

class UserPerfil(models.Model):
    descricao = models.TextField(null=True, blank=True)
    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentual máximo de desconto que um usuário com este perfil pode conceder.",
    )   

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"
        

class User(AbstractUser):
    # username/email padrões do Django
    pin_hash = models.CharField(max_length=256, null=True, blank=True)
    perfil = models.ForeignKey(UserPerfil, on_delete=models.SET_NULL, null=True, blank=True)

class UserFilial(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filial_id = models.UUIDField()
    class Meta:
        unique_together = ("user","filial_id")
