"""REST API views for the dashboard.

Endpoints
---------
GET /api/runs/
    List the 50 most recent experiment runs.

GET /api/runs/{run_id}/series/
    Return PipelineCycle time-series data for a run.

    Query params:
        slice  -- one of "train", "validation", "test" (default: all)
        limit  -- max rows returned (default 2 000, max 10 000)
        stride -- sample every Nth cycle for large datasets (default 1)

GET /api/runs/{run_id}/metrics/
    Return EvaluationSummary metrics for each data slice of a run.
"""

from django.http import Http404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle

from .serializers import (
    CycleSerializer,
    EvaluationSummarySerializer,
    RunListSerializer,
)

_VALID_SLICES = frozenset({"train", "validation", "test"})
_DEFAULT_LIMIT = 2_000
_MAX_LIMIT = 10_000


class RunListView(APIView):
    """List the 50 most recent experiment runs."""

    def get(self, request: Request) -> Response:
        runs = ExperimentRun.objects.order_by("-created_at")[:50]
        return Response(RunListSerializer(runs, many=True).data)


class RunSeriesView(APIView):
    """Return PipelineCycle rows for charting."""

    def get(self, request: Request, run_id: int) -> Response:
        try:
            run = ExperimentRun.objects.get(pk=run_id)
        except ExperimentRun.DoesNotExist:
            raise Http404

        slice_type = request.query_params.get("slice", None)
        limit = min(
            int(request.query_params.get("limit", _DEFAULT_LIMIT)),
            _MAX_LIMIT,
        )
        stride = max(int(request.query_params.get("stride", 1)), 1)

        qs = PipelineCycle.objects.filter(run=run).order_by("cycle_index")
        if slice_type in _VALID_SLICES:
            qs = qs.filter(slice_type=slice_type)

        total = qs.count()

        if stride == 1:
            result_qs = qs[:limit]
        else:
            all_ids = list(qs.values_list("id", flat=True))
            sampled_ids = all_ids[::stride][:limit]
            result_qs = PipelineCycle.objects.filter(id__in=sampled_ids).order_by(
                "cycle_index"
            )

        return Response(
            {
                "run_id": run.pk,
                "run_name": run.name,
                "run_status": run.status,
                "total_cycles": total,
                "returned": result_qs.count(),
                "data": CycleSerializer(result_qs, many=True).data,
            }
        )


class RunMetricsView(APIView):
    """Return EvaluationSummary metrics per data slice."""

    def get(self, request: Request, run_id: int) -> Response:
        try:
            run = ExperimentRun.objects.get(pk=run_id)
        except ExperimentRun.DoesNotExist:
            raise Http404

        summaries = EvaluationSummary.objects.filter(run=run)
        return Response(
            {
                "run_id": run.pk,
                "run_name": run.name,
                "slices": {
                    s.slice_type: EvaluationSummarySerializer(s).data
                    for s in summaries
                },
            }
        )
