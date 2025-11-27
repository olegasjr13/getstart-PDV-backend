# produtos/views/grupo_produto_views.py

from rest_framework import viewsets, permissions, filters

from produtos.models import GrupoProduto
from produtos.serializers.grupo_produto_serializers import GrupoProdutoSerializer


class GrupoProdutoViewSet(viewsets.ModelViewSet):
    """
    CRUD de Grupo de Produto.

    Isolação multi-tenant é garantida pelo schema atual (django-tenants).
    """

    serializer_class = GrupoProdutoSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = GrupoProduto.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["nome", "descricao"]
