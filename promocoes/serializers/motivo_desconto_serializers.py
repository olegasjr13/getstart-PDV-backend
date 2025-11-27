from rest_framework import serializers

from promocoes.models.motivo_desconto_models import MotivoDesconto

class MotivoDescontoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MotivoDesconto
        fields = '__all__'