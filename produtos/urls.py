# produtos/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from produtos.views.grupo_produto_views import GrupoProdutoViewSet
from produtos.views.produto_views import ProdutoViewSet
from produtos.views.produto_codigo_barras_views import (
    ProdutoCodigoBarrasViewSet,
)

router = DefaultRouter()
router.register(r"grupos-produtos", GrupoProdutoViewSet, basename="grupoproduto")
router.register(r"produtos", ProdutoViewSet, basename="produto")
router.register(
    r"produtos-codigos-barras",
    ProdutoCodigoBarrasViewSet,
    basename="produto-codigobarras",
)

urlpatterns = [
    path("", include(router.urls)),
]
