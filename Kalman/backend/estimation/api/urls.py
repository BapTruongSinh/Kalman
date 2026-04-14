"""URL patterns for the estimation REST API."""

from django.urls import path

from . import ingest, views

urlpatterns = [
    # Dashboard read-only endpoints (unauthenticated)
    path("runs/", views.RunListView.as_view(), name="run-list"),
    path("runs/<int:run_id>/series/", views.RunSeriesView.as_view(), name="run-series"),
    path("runs/<int:run_id>/metrics/", views.RunMetricsView.as_view(), name="run-metrics"),
    # Live sensor ingestion (requires Token auth)
    path("ingest/samples/", ingest.LiveIngestView.as_view(), name="live-ingest"),
]
