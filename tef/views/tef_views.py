# tef/views/tef_views.py

from rest_framework import viewsets, permissions, filters


from tef.models.tef_models import TefConfig
from tef.serializers.tef_serializers import TefConfigSerializer


class TefConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD de configurações TEF.

    - Multi-tenant: isolamento garantido pelo schema atual (django-tenants).
    - Escopos:
        * Filial + provider, com terminal NULL => config padrão.
        * Filial + provider + terminal => config específica para o terminal.
    """

    serializer_class = TefConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = TefConfig.objects.all().order_by("filial__id", "terminal__id", "provider")

    filter_backends = [filters.SearchFilter]
    search_fields = ["filial__nome_fantasia", "merchant_id", "store_id", "provider"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Aqui você pode futuramente filtrar por empresa/tenant se tiver vínculo com usuário.
        return qs
