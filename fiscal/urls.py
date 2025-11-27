# fiscal/urls.py

from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter

from fiscal.views import nfce_contingencia_views
from fiscal.views.ncm_views import NCMViewSet
from fiscal.views.nfce_inutilizacao_views import inutilizar_faixa_nfce_view
from fiscal.views.nfce_pre_emissao_views import pre_emissao
from fiscal.views.nfce_views import reservar_numero
from fiscal.views.nfce_emissao_views import emitir_nfce_view
from fiscal.views.nfce_cancelamento_views import cancelar_nfce_view

app_name = "fiscal"

# Router para NCM (ViewSet)
router = DefaultRouter()
router.register(r"ncm", NCMViewSet, basename="ncm")

urlpatterns = [
    # Endpoints de NCM (list, retrieve, etc) em /fiscal/ncm/
    # Ex: GET /api/v1/fiscal/ncm/  e GET /api/v1/fiscal/ncm/<id>/
    path("", include(router.urls)),

    # nfce - reservar número
    path("nfce/reservar-numero", reservar_numero, name="nfce_reservar_numero"),
    path("nfce/reservar-numero/", reservar_numero),

    # nfce - pré-emissão
    path("nfce/pre-emissao", pre_emissao),
    path("nfce/pre-emissao/", pre_emissao),

    # nfce - emissão
    path("nfce/emitir", emitir_nfce_view, name="nfce_emitir"),
    path("nfce/emitir/", emitir_nfce_view),

    # tolerância a barras extras
    re_path(r"^nfce/reservar-numero/*$", reservar_numero),

    # nfce - cancelamento
    path("nfce/cancelar", cancelar_nfce_view, name="nfce_cancelar"),
    path("nfce/cancelar/", cancelar_nfce_view),

    # nfce - inutilização de faixa
    path("nfce/inutilizar", inutilizar_faixa_nfce_view, name="nfce_inutilizar"),
    path("nfce/inutilizar/", inutilizar_faixa_nfce_view),

    path(
        "nfce/regularizar-contingencia/",
        nfce_contingencia_views.nfce_regularizar_contingencia_view,
        name="nfce-regularizar-contingencia",
    ),
    path(
        "nfce/regularizar-contingencia",
        nfce_contingencia_views.nfce_regularizar_contingencia_view,
        name="nfce-regularizar-contingencia",
    ),
]
