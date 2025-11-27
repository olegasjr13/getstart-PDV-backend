# produtos/serializers/produto_serializers.py

from rest_framework import serializers

from produtos.models import Produto, GrupoProduto, UnidadeMedida
from fiscal.models import NCM


class ProdutoSerializer(serializers.ModelSerializer):
    grupo_nome = serializers.CharField(source="grupo.nome", read_only=True)
    ncm_codigo = serializers.CharField(source="ncm.codigo", read_only=True)
    unidade_comercial_sigla = serializers.CharField(
        source="unidade_comercial.sigla", read_only=True
    )
    unidade_tributavel_sigla = serializers.CharField(
        source="unidade_tributavel.sigla", read_only=True
    )

    class Meta:
        model = Produto
        fields = [
            "id",
            "codigo_interno",
            "descricao",
            "descricao_complementar",
            "grupo",
            "grupo_nome",
            "ncm",
            "ncm_codigo",
            "unidade_comercial",
            "unidade_comercial_sigla",
            "unidade_tributavel",
            "unidade_tributavel_sigla",
            "fator_conversao_tributavel",
            "peso_liquido_kg",
            "peso_bruto_kg",
            "origem_mercadoria",
            "cfop_venda_dentro_estado",
            "cfop_venda_fora_estado",
            "csosn_icms",
            "aliquota_icms",
            "cst_pis",
            "cst_cofins",
            "aliquota_pis",
            "aliquota_cofins",
            "cst_ipi",
            "codigo_enquadramento_ipi",
            "aliquota_ipi",
            "aliquota_cbs_especifica",
            "aliquota_ibs_especifica",
            "permite_fracionar",
            "rastreavel",
            "imagem",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Reaproveita as validações de model.clean() + garantias extras.
        """
        instance = Produto(**attrs)
        instance.clean()
        return attrs
