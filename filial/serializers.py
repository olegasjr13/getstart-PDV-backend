from rest_framework import serializers
from .models.filial_models import Filial

class FilialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filial
        fields = ("id","cnpj","nome_fantasia","uf","csc_id","ambiente","a1_expires_at")
