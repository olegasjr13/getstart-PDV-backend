# fiscal/serializers_emissao.py
from rest_framework import serializers


class EmitirNfceInputSerializer(serializers.Serializer):
    """
    Dados de entrada para emissão NFC-e via API.

    A emissão é feita a partir de um request_id previamente utilizado
    na pré-emissão (NfcePreEmissao).
    """

    request_id = serializers.UUIDField()


class EmitirNfceOutputSerializer(serializers.Serializer):
    """
    Dados de saída da emissão NFC-e via API.

    Espelha o DTO EmitirNfceResult retornado pela service
    fiscal.services.emissao_service.emitir_nfce.
    """

    request_id = serializers.CharField()
    numero = serializers.IntegerField()
    serie = serializers.IntegerField()
    filial_id = serializers.CharField()
    terminal_id = serializers.CharField()

    chave_acesso = serializers.CharField()
    protocolo = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField()

    xml_autorizado = serializers.CharField(allow_blank=True, allow_null=True)
    mensagem = serializers.CharField(allow_blank=True, allow_null=True)
