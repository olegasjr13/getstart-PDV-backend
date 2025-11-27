# produtos/views/produto_codigo_barras_views.py

from rest_framework import viewsets, permissions, filters

from produtos.models import ProdutoCodigoBarras
from produtos.serializers.produto_codigo_barras_serializers import (
    ProdutoCodigoBarrasSerializer,
)


class ProdutoCodigoBarrasViewSet(viewsets.ModelViewSet):
    """
    CRUD de códigos de barras de Produto (múltiplos por produto).

    A integridade (apenas um principal por função/produto) é garantida
    pelos constraints de banco.
    """

    serializer_class = ProdutoCodigoBarrasSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProdutoCodigoBarras.objects.select_related("produto")
    filter_backends = [filters.SearchFilter]
    search_fields = ["codigo", "produto__codigo_interno", "produto__descricao"]
