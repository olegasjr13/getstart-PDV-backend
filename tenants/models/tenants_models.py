from django.db import models
from django.forms import BooleanField
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    cnpj_raiz = models.CharField(max_length=14, unique=True)  # X-Tenant-ID
    nome = models.CharField(max_length=150)
    premium_db_alias = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_create_schema = True
    active = BooleanField(default=True)

class Domain(DomainMixin):
    pass
