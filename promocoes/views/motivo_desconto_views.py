from rest_framework import viewsets, filters

from promocoes.models.motivo_desconto_models import MotivoDesconto
from promocoes.serializers.motivo_desconto_serializers import MotivoDescontoSerializer
class MotivoDescontoViewSet(viewsets.ModelViewSet):
    queryset = MotivoDesconto.objects.all()
    serializer_class = MotivoDescontoSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome', 'codigo_nfe']