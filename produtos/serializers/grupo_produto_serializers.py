# produtos/serializers/grupo_produto_serializers.py

from rest_framework import serializers

from produtos.models import GrupoProduto


class GrupoProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrupoProduto
        fields = [
            "id",
            "nome",
            "descricao",
            "imagem",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
