# config/urls.py
from django.contrib import admin
from django.urls import path, include

from vendas.api.v1.views import FinalizarVendaNfceView

urlpatterns = [
    path("api/v1/usuario/", include("usuario.urls")),
    path("api/v1/filial/", include("filial.urls")),
    path("api/v1/terminal/", include("terminal.urls")),
    path("api/v1/fiscal/", include(("fiscal.urls", "fiscal"), namespace="fiscal")),
    path("api/v1/endereco/", include(("enderecos.urls", "enderecos"), namespace="enderecos")),
    path(
        "api/v1/tenants/",
        include(("tenants.urls", "tenants"), namespace="tenants"),
    ),
    path("api/v1/produtos/", include("produtos.urls")),
    path("api/v1/metodos-pagamento/", include("metodoPagamento.urls")),
    path("api/tef/", include("tef.urls")),
    path("api/v1/promocoes/", include("promocoes.urls")),

    path(
        "api/v1/pdv/vendas/<uuid:venda_id>/finalizar-nfce/",
        FinalizarVendaNfceView.as_view(),
        name="pdv-venda-finalizar-nfce",
    ),

]
