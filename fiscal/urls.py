# fiscal/urls.py
from django.urls import path, re_path

from fiscal.views.nfce_pre_emissao_views import pre_emissao
from fiscal.views.nfce_views import reservar_numero

app_name = "fiscal"

urlpatterns = [
    # nfce - reservar número
    path("nfce/reservar-numero", reservar_numero, name="nfce_reservar_numero"),
    path("nfce/reservar-numero/", reservar_numero),
    path("nfce/pre-emissao", pre_emissao),
    path("nfce/pre-emissao/", pre_emissao),

    # tolerância a barras extras
    re_path(r"^nfce/reservar-numero/*$", reservar_numero),
]
