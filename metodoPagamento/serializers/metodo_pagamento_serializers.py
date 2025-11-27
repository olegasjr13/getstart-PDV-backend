# metodoPagamento/serializers/metodo_pagamento_serializers.py

from rest_framework import serializers

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento



class MetodoPagamentoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = MetodoPagamento
        fields = [
            "id",
            "codigo",
            "tipo",
            "tipo_display",
            "descricao",
            "utiliza_tef",
            "codigo_fiscal",
            "codigo_tef",
            "desconto_automatico_percentual",
            "permite_parcelamento",
            "max_parcelas",
            "valor_minimo_parcela",
            "permite_troco",
            "ordem_exibicao",
            "permite_desconto",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Reaproveita as validações de model.clean() + garantias extras.
        Segue o mesmo padrão usado em Produto.
        """
        # Para updates parciais (PATCH), precisamos compor um "pseudo-instance"
        # com os dados atuais + attrs novos.
        instance = MetodoPagamento(
            **{
                **getattr(self.instance, "__dict__", {}),
                **attrs,
            }
        )
        # Remove campos internos do Django que não interessam ao clean()
        instance.__dict__.pop("_state", None)

        instance.clean()
        return attrs
