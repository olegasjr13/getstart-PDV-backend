# fiscal/serializers/ncm_serializers.py

from rest_framework import serializers

from fiscal.models import NCM


class NCMSerializer(serializers.ModelSerializer):
    class Meta:
        model = NCM
        fields = [
            "id",
            "codigo",
            "descricao",
            "vigencia_inicio",
            "vigencia_fim",
            "versao_tabela",
            "observacoes",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
