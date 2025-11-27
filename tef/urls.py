# tef/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from tef.views.tef_views import TefConfigViewSet



router = DefaultRouter()
router.register(r"configs-tef", TefConfigViewSet, basename="tefconfig")

urlpatterns = [
    path("", include(router.urls)),
]
