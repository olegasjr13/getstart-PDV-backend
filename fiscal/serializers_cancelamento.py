# fiscal/serializers_cancelamento.py

from rest_framework import serializers


class CancelarNfceInputSerializer(serializers.Serializer):
    """
    Dados de entrada para cancelamento de NFC-e.

    É obrigatório informar:
      - chave_acesso
        OU
      - (filial_id, numero, serie)
    """

    chave_acesso = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Chave de acesso completa da NFC-e (se informada, tem prioridade).",
    )
    filial_id = serializers.UUIDField(
        required=False,
        help_text="Identificador da filial, caso a busca seja por (filial, numero, serie).",
    )
    numero = serializers.IntegerField(required=False, min_value=1)
    serie = serializers.IntegerField(required=False, min_value=1)

    motivo = serializers.CharField(
        required=True,
        help_text="Motivo descritivo do cancelamento. Requerido pela SEFAZ.",
    )

    def validate(self, attrs):
        chave_acesso = attrs.get("chave_acesso") or ""
        filial_id = attrs.get("filial_id")
        numero = attrs.get("numero")
        serie = attrs.get("serie")

        if not chave_acesso and not (filial_id and numero is not None and serie is not None):
            raise serializers.ValidationError(
                "Informe a chave_acesso ou a combinação (filial_id, numero, serie)."
            )

        motivo = attrs.get("motivo") or ""
        if len(motivo.strip()) < 15:
            raise serializers.ValidationError(
                {"motivo": "Motivo de cancelamento muito curto (mínimo 15 caracteres)."}
            )

        return attrs


class CancelarNfceOutputSerializer(serializers.Serializer):
    """
    Dados de saída do cancelamento NFC-e via API.
    """

    request_id = serializers.CharField()
    filial_id = serializers.CharField()
    terminal_id = serializers.CharField()
    numero = serializers.IntegerField()
    serie = serializers.IntegerField()
    chave_acesso = serializers.CharField()
    protocolo = serializers.CharField()
    status = serializers.CharField()
    mensagem = serializers.CharField()
