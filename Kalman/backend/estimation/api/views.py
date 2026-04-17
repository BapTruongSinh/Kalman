"""Các REST API view cho dashboard.

Endpoint
--------
GET /api/runs/
    Liệt kê 50 experiment run mới nhất.

GET /api/runs/{run_id}/series/
    Trả dữ liệu time-series PipelineCycle của một run.

    Query params:
        slice  -- tùy chọn; nếu có thì phải là ``train``, ``validation`` hoặc
                  ``test``. Bỏ qua param này để lấy mọi slice.
        limit  -- số dòng tối đa trả về (mặc định 2 000, tối đa 10 000; >= 1)
        stride -- lấy mẫu mỗi N cycle (mặc định 1, tối đa 1 000).
                  ``limit * stride`` không được vượt 100 000 để tránh DoS.

GET /api/runs/{run_id}/metrics/
    Trả metric EvaluationSummary cho từng slice dữ liệu của một run.
"""

from django.http import Http404
from rest_framework import status
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
_MAX_STRIDE = 1_000
# Chặn số dòng xét khi stride > 1, tránh quét limit * stride lên tới hàng triệu ID.
_MAX_LIMIT_STRIDE_PRODUCT = 100_000


def _parse_positive_int(raw: str, default: int, max_value: int) -> tuple[int, str | None]:
    """Parse *raw* thành số nguyên dương và chặn trong [1, max_value].

    Thành công thì trả ``(value, None)``, lỗi thì trả ``(0, error_message)``.
    """
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return 0, f"'{raw}' is not a valid integer."
    if value < 1:
        return 0, f"Value must be >= 1, got {value}."
    return min(value, max_value), None


class RunListView(APIView):
    """Liệt kê 50 experiment run mới nhất."""

    def get(self, request: Request) -> Response:
        runs = ExperimentRun.objects.order_by("-created_at")[:50]
        return Response(RunListSerializer(runs, many=True).data)


class RunSeriesView(APIView):
    """Trả các dòng PipelineCycle để vẽ biểu đồ."""

    def get(self, request: Request, run_id: int) -> Response:
        try:
            run = ExperimentRun.objects.get(pk=run_id)
        except ExperimentRun.DoesNotExist:
            raise Http404

        # -- Parse và validate query param ------------------------------------
        raw_limit = request.query_params.get("limit", str(_DEFAULT_LIMIT))
        limit, limit_err = _parse_positive_int(raw_limit, _DEFAULT_LIMIT, _MAX_LIMIT)
        if limit_err:
            return Response({"error": f"limit: {limit_err}"}, status=status.HTTP_400_BAD_REQUEST)

        raw_stride = request.query_params.get("stride", "1")
        stride, stride_err = _parse_positive_int(raw_stride, 1, _MAX_STRIDE)
        if stride_err:
            return Response({"error": f"stride: {stride_err}"}, status=status.HTTP_400_BAD_REQUEST)

        product = limit * stride
        if product > _MAX_LIMIT_STRIDE_PRODUCT:
            return Response(
                {
                    "error": (
                        f"limit * stride must be <= {_MAX_LIMIT_STRIDE_PRODUCT} "
                        f"(got {product}). Reduce limit or stride."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "slice" in request.query_params:
            raw_slice = (request.query_params.get("slice") or "").strip().lower()
            if raw_slice not in _VALID_SLICES:
                return Response(
                    {
                        "error": (
                            "slice: must be one of train, validation, test "
                            f"(got {request.query_params.get('slice')!r}). Omit slice for all slices."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            slice_type: str | None = raw_slice
        else:
            slice_type = None

        # -- Tạo queryset -----------------------------------------------------
        qs = PipelineCycle.objects.filter(run=run).order_by("cycle_index")
        if slice_type is not None:
            qs = qs.filter(slice_type=slice_type)

        total = qs.count()

        # -- Áp dụng stride + limit ------------------------------------------
        if stride == 1:
            result_qs = qs[:limit]
        else:
            # Giới hạn scan ID tối đa (limit * stride) dòng, để run lớn không
            # kéo toàn bộ cycle ID vào bộ nhớ Python.
            candidate_ids = list(
                qs.values_list("id", flat=True)[: limit * stride]
            )
            sampled_ids = candidate_ids[::stride][:limit]
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
    """Trả metric EvaluationSummary theo từng slice dữ liệu."""

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
