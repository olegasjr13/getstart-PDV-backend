from django.urls import path
from .views.commons_views import liveness, readiness, time_now

urlpatterns = [
    path("health/liveness", liveness),
    path("health/readiness", readiness),
    path("time/now", time_now),
]
