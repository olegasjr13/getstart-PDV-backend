# produtos/views/produto_views.py

from rest_framework import viewsets, permissions, filters

from produtos.models import Produto
from produtos.serializers.produto_serializers import ProdutoSerializer


class ProdutoViewSet(viewsets.ModelViewSet):
    """
    CRUD de Produto, pronto para emissão fiscal.

    Multi-tenant: cada schema tem sua própria tabela de produtos.
    """

    serializer_class = ProdutoSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Produto.objects.select_related(
        "grupo", "ncm", "unidade_comercial", "unidade_tributavel"
    )
    filter_backends = [filters.SearchFilter]
    search_fields = ["codigo_interno", "descricao"]

    def get_queryset(self):
        """
        Ponto central para futuras regras (ex: filtrar apenas ativos
        em endpoints públicos, etc).
        """
        qs = super().get_queryset()
        return qs
