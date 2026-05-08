"""Cấu hình URL cấp project cho backend Kalman pipeline."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("estimation.api.urls")),
]
