"""Project-level URL configuration for the Kalman pipeline backend."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("estimation.api.urls")),
]
