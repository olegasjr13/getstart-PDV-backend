from rest_framework import serializers


class InutilizarFaixaNfceInputSerializer(serializers.Serializer):
    """
    Dados de entrada para inutilização de faixa numérica de NFC-e.
    """

    filial_id = serializers.UUIDField()
    serie = serializers.IntegerField(min_value=1)
    numero_inicial = serializers.IntegerField(min_value=1)
    numero_final = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField()
    request_id = serializers.UUIDField()

    def validate(self, attrs):
        numero_inicial = attrs.get("numero_inicial")
        numero_final = attrs.get("numero_final")
        motivo = attrs.get("motivo") or ""

        if numero_inicial > numero_final:
            raise serializers.ValidationError(
                {"numero_inicial": "numero_inicial não pode ser maior que numero_final."}
            )

        if len(motivo.strip()) < 15:
            raise serializers.ValidationError(
                {"motivo": "Motivo de inutilização muito curto (mínimo 15 caracteres)."}
            )

        return attrs


class InutilizarFaixaNfceOutputSerializer(serializers.Serializer):
    """
    Dados de saída da inutilização de faixa NFC-e.
    """

    request_id = serializers.CharField()
    filial_id = serializers.CharField()
    serie = serializers.IntegerField()
    numero_inicial = serializers.IntegerField()
    numero_final = serializers.IntegerField()
    protocolo = serializers.CharField()
    status = serializers.CharField()
    mensagem = serializers.CharField()
