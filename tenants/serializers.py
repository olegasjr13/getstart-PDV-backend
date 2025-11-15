from rest_framework import serializers

class TenantCreateSerializer(serializers.Serializer):
    cnpj_raiz = serializers.RegexField(regex=r"^\d{14}$")
    nome = serializers.CharField(max_length=150)
    domain = serializers.CharField(max_length=255)
    premium_db_alias = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
