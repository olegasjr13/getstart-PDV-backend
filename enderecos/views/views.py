from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from enderecos.models.pais_models import Pais
from enderecos.models.uf_models import UF
from enderecos.models.municipio_models import Municipio
from enderecos.models.bairro_models import Bairro
from enderecos.models.logradouro_models import Logradouro
from enderecos.models.endereco_models import Endereco

from enderecos.serializers import (
    PaisSerializer, UFSerializer, MunicipioSerializer,
    BairroSerializer, LogradouroSerializer, EnderecoSerializer
)

class PaisViewSet(viewsets.ModelViewSet):
    queryset = Pais.objects.all()
    serializer_class = PaisSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome', 'codigo_nfe']

class UFViewSet(viewsets.ModelViewSet):
    queryset = UF.objects.all()
    serializer_class = UFSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['pais']
    search_fields = ['nome', 'sigla']

class MunicipioViewSet(viewsets.ModelViewSet):
    queryset = Municipio.objects.all()
    serializer_class = MunicipioSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['uf'] # Filtrar municípios por UF (essencial para combos)
    search_fields = ['nome', 'codigo_ibge']

class BairroViewSet(viewsets.ModelViewSet):
    queryset = Bairro.objects.all()
    serializer_class = BairroSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['municipio']
    search_fields = ['nome']

class LogradouroViewSet(viewsets.ModelViewSet):
    queryset = Logradouro.objects.all()
    serializer_class = LogradouroSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['bairro', 'cep'] # Busca por CEP exato
    search_fields = ['nome', 'cep']

class EnderecoViewSet(viewsets.ModelViewSet):
    queryset = Endereco.objects.all()
    serializer_class = EnderecoSerializer
    # Permite filtrar endereços por logradouro
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['logradouro']