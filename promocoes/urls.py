# promocoes/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from promocoes.views.motivo_desconto_views import MotivoDescontoViewSet


router = DefaultRouter()
router.register(r"motivo-desconto", MotivoDescontoViewSet, basename="motivodesconto")

urlpatterns = [
    path("", include(router.urls)),
]
