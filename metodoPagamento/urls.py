# metodoPagamento/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from metodoPagamento.views.metodo_pagamento_views import MetodoPagamentoViewSet


router = DefaultRouter()
router.register(
    r"metodos-pagamento",
    MetodoPagamentoViewSet,
    basename="metodopagamento",
)

urlpatterns = [
    path("", include(router.urls)),
]
