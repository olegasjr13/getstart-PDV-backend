# metodoPagamento/serializers/filial_metodo_pagamento_serializers.py

from rest_framework import serializers

from metodoPagamento.models.filial_metodo_pagamento_models import FilialMetodoPagamento




class FilialMetodoPagamentoSerializer(serializers.ModelSerializer):
    filial_nome = serializers.CharField(
        source="filial.nome_fantasia", read_only=True
    )
    metodo_pagamento_descricao = serializers.CharField(
        source="metodo_pagamento.descricao", read_only=True
    )

    class Meta:
        model = FilialMetodoPagamento
        fields = [
            "id",
            "filial",
            "filial_nome",
            "metodo_pagamento",
            "metodo_pagamento_descricao",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Aqui dá para colocar validações extras no futuro, como:
        - Não permitir ativar método inativo ou filial inativa.
        Por enquanto, mantemos simples e deixamos a regra para a camada de domínio.
        """
        return super().validate(attrs)
