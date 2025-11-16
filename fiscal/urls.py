# fiscal/urls.py
from django.urls import path, re_path

from fiscal.views.nfce_pre_emissao_views import pre_emissao
from fiscal.views.nfce_views import reservar_numero
from fiscal.views.nfce_emissao_views import emitir_nfce_view
from fiscal.views.nfce_cancelamento_views import cancelar_nfce_view

app_name = "fiscal"

urlpatterns = [
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

]
