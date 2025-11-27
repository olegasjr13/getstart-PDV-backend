# enderecos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from enderecos.views.views import BairroViewSet, EnderecoViewSet, LogradouroViewSet, MunicipioViewSet, PaisViewSet, UFViewSet

# Cria o roteador padrão
router = DefaultRouter()

# Registra os ViewSets
router.register(r'pais', PaisViewSet, basename='pais')
router.register(r'uf', UFViewSet, basename='uf')
router.register(r'municipio', MunicipioViewSet, basename='municipio')
router.register(r'bairro', BairroViewSet, basename='bairro')
router.register(r'logradouro', LogradouroViewSet, basename='logradouro')
router.register(r'endereco', EnderecoViewSet, basename='endereco')

urlpatterns = [
    path('', include(router.urls)),
]