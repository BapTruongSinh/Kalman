"""URL pattern cho REST API của estimation."""

from django.urls import path

from . import ingest, views

urlpatterns = [
    # Endpoint chỉ đọc cho dashboard, không bắt xác thực ở development.
    path("runs/", views.RunListView.as_view(), name="run-list"),
    path("runs/<int:run_id>/series/", views.RunSeriesView.as_view(), name="run-series"),
    path("runs/<int:run_id>/metrics/", views.RunMetricsView.as_view(), name="run-metrics"),
    path(
        "greenhouses/<int:greenhouse_id>/control-profile/",
        views.GreenhouseControlProfileView.as_view(),
        name="greenhouse-control-profile",
    ),
    path(
        "greenhouses/<int:greenhouse_id>/ampc/recommendations/",
        views.AMPCRecommendationCreateView.as_view(),
        name="ampc-recommendation-create",
    ),
    path(
        "greenhouses/<int:greenhouse_id>/ampc/recommendations/latest/",
        views.AMPCLatestRecommendationView.as_view(),
        name="ampc-recommendation-latest",
    ),
    # Nạp sensor live, cần Token auth.
    path("ingest/samples/", ingest.LiveIngestView.as_view(), name="live-ingest"),
]
