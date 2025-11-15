from django.urls import path
from .views.terminal_views import reservar_numeracao

urlpatterns = [
    path(
        "terminais/<uuid:id>/reservar-numeracao",
        reservar_numeracao,
        name="terminal_reservar_numeracao_legacy",
    ),
]
