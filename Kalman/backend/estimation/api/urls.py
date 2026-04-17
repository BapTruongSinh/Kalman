"""URL pattern cho REST API của estimation."""

from django.urls import path

from . import ingest, views

urlpatterns = [
    # Endpoint chỉ đọc cho dashboard, không bắt xác thực ở development.
    path("runs/", views.RunListView.as_view(), name="run-list"),
    path("runs/<int:run_id>/series/", views.RunSeriesView.as_view(), name="run-series"),
    # Nạp sensor live, cần Token auth.
    path("ingest/samples/", ingest.LiveIngestView.as_view(), name="live-ingest"),
]
