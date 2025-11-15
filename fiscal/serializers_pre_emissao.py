# fiscal/serializers_pre_emissao.py
from rest_framework import serializers

class PreEmissaoInputSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    payload = serializers.JSONField()


class PreEmissaoOutputSerializer(serializers.Serializer):
    id = serializers.CharField()
    numero = serializers.IntegerField()
    serie = serializers.IntegerField()
    filial_id = serializers.CharField()
    terminal_id = serializers.CharField()
    request_id = serializers.CharField()
    payload = serializers.JSONField()
    created_at = serializers.CharField()
