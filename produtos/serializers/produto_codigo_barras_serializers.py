# produtos/serializers/produto_codigo_barras_serializers.py

from rest_framework import serializers

from produtos.models import ProdutoCodigoBarras


class ProdutoCodigoBarrasSerializer(serializers.ModelSerializer):
    produto_codigo_interno = serializers.CharField(
        source="produto.codigo_interno", read_only=True
    )
    produto_descricao = serializers.CharField(
        source="produto.descricao", read_only=True
    )

    class Meta:
        model = ProdutoCodigoBarras
        fields = [
            "id",
            "produto",
            "produto_codigo_interno",
            "produto_descricao",
            "codigo",
            "tipo_barra",
            "funcao",
            "principal",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
