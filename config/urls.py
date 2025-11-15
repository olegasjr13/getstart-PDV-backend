from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),       # admin por tenant
    path("api/v1/", include("commons.urls")),
    path("api/v1/", include("tenants.urls")),
    path("api/v1/", include("usuario.urls")),
    path("api/v1/", include("filial.urls")),
    path("api/v1/", include("terminal.urls")),
    path("api/v1/fiscal/", include(("fiscal.urls", "fiscal"), namespace="fiscal")),

]
