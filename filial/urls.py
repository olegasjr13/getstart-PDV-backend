from django.urls import path
from .views.filial_views import filial_detail
urlpatterns = [ path("filiais/<uuid:id>", filial_detail) ]
