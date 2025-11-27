# fiscal/views/ncm_views.py

from rest_framework import viewsets, permissions, filters

from fiscal.models import NCM
from fiscal.ncm_serializers import NCMSerializer



class NCMViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API de consulta de NCM.

    - Atualização é feita apenas via management command (atualizar_ncm).
    """

    serializer_class = NCMSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = NCM.objects.filter(ativo=True)
    filter_backends = [filters.SearchFilter]
    search_fields = ["codigo", "descricao"]
