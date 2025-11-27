# metodoPagamento/views/metodo_pagamento_views.py

from rest_framework import viewsets, permissions, filters

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from metodoPagamento.serializers.metodo_pagamento_serializers import MetodoPagamentoSerializer




class MetodoPagamentoViewSet(viewsets.ModelViewSet):
    """
    CRUD de Métodos de Pagamento.

    Este cadastro é o hub entre:
    - Venda (domínio PDV)
    - TEF/SITEF (quando utiliza_tef=True)
    - Emissão fiscal (mapeamento codigo_fiscal NFe/NFC-e)

    Multi-tenant:
    - Isolação garantida via schema atual (django-tenants).
    """

    serializer_class = MetodoPagamentoSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = MetodoPagamento.objects.all().order_by("ordem_exibicao", "codigo")

    filter_backends = [filters.SearchFilter]
    search_fields = ["codigo", "descricao"]

    def get_queryset(self):
        """
        Ponto central para futuras regras:
        - Filtrar apenas ativos para o PDV on-line;
        - Aplicar escopos por filial, etc.

        Por enquanto, retorna todos os métodos.
        """
        qs = super().get_queryset()
        return qs.filter(ativo=True)
