# fiscal/serializers.py
from rest_framework import serializers


class ReservarNumeroInputSerializer(serializers.Serializer):
    # força validação de UUID antes de chegar na service
    terminal_id = serializers.UUIDField()
    # faixa de exemplo; ajuste se a regra de negócio permitir outros valores
    serie = serializers.IntegerField(min_value=1, max_value=999)
    request_id = serializers.UUIDField()


class ReservarNumeroOutputSerializer(serializers.Serializer):
    numero = serializers.IntegerField()
    serie = serializers.IntegerField()
    terminal_id = serializers.UUIDField()
    filial_id = serializers.UUIDField()
    request_id = serializers.UUIDField() 
    reserved_at = serializers.DateTimeField()
