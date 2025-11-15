from rest_framework import serializers

class ReservaNumeracaoResponse(serializers.Serializer):
    numero = serializers.IntegerField()
    serie = serializers.IntegerField()
