"""Các REST API view cho dashboard.

Endpoint
--------
GET /api/runs/
    Liệt kê 50 experiment run mới nhất.

GET /api/runs/{run_id}/series/
    Trả dữ liệu time-series PipelineCycle của một run.

    Query params:
        slice  -- tùy chọn; nếu có thì phải là ``online``.
        limit  -- số dòng tối đa trả về (mặc định 2 000, tối đa 10 000; >= 1)
        stride -- lấy mẫu mỗi N cycle (mặc định 1, tối đa 1 000).
                  ``limit * stride`` không được vượt 100 000 để tránh DoS.

GET /api/runs/{run_id}/metrics/
    Trả metric EvaluationSummary cho từng slice dữ liệu của một run.
"""

from django.http import Http404
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from estimation.control.service import (
    AMPCForbidden,
    AMPCNotFound,
    get_owned_profile,
    latest_recommendation_for_user,
    run_ampc_for_greenhouse,
)
from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle

from .serializers import (
    AMPCRecommendationSerializer,
    CycleSerializer,
    EvaluationSummarySerializer,
    GreenhouseControlProfileSerializer,
    RunListSerializer,
)

_VALID_SLICES = frozenset({"online"})
_DEFAULT_LIMIT = 2_000
_MAX_LIMIT = 10_000
_MAX_STRIDE = 1_000
# Chặn số dòng xét khi stride > 1, tránh quét limit * stride lên tới hàng triệu ID.
_MAX_LIMIT_STRIDE_PRODUCT = 100_000
_MAX_ID_VALUE = 2_147_483_647


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


def _run_queryset_for_request(request: Request):
    qs = ExperimentRun.objects.select_related("greenhouse").order_by("-created_at")
    if request.user.is_authenticated:
        qs = qs.filter(greenhouse__owner=request.user)
    return qs


def _get_run_for_request(request: Request, run_id: int) -> ExperimentRun:
    try:
        return _run_queryset_for_request(request).get(pk=run_id)
    except ExperimentRun.DoesNotExist:
        raise Http404


class RunListView(APIView):
    """Liệt kê 50 experiment run mới nhất."""

    def get(self, request: Request) -> Response:
        qs = _run_queryset_for_request(request)
        if "greenhouse_id" in request.query_params:
            greenhouse_id, parse_err = _parse_positive_int(
                request.query_params.get("greenhouse_id"),
                0,
                _MAX_ID_VALUE,
            )
            if parse_err:
                return Response(
                    {"error": f"greenhouse_id: {parse_err}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(greenhouse_id=greenhouse_id)
        runs = qs[:50]
        return Response(RunListSerializer(runs, many=True).data)


class RunSeriesView(APIView):
    """Trả các dòng PipelineCycle để vẽ biểu đồ."""

    def get(self, request: Request, run_id: int) -> Response:
        run = _get_run_for_request(request, run_id)

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
                            "slice: must be 'online' "
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
                "greenhouse_id": run.greenhouse_id,
                "greenhouse_name": run.greenhouse.name,
                "run_status": run.status,
                "total_cycles": total,
                "returned": result_qs.count(),
                "data": CycleSerializer(result_qs, many=True).data,
            }
        )


class RunMetricsView(APIView):
    """Trả metric EvaluationSummary theo từng slice dữ liệu."""

    def get(self, request: Request, run_id: int) -> Response:
        run = _get_run_for_request(request, run_id)

        summaries = EvaluationSummary.objects.filter(run=run)
        return Response(
            {
                "run_id": run.pk,
                "run_name": run.name,
                "greenhouse_id": run.greenhouse_id,
                "greenhouse_name": run.greenhouse.name,
                "slices": {
                    s.slice_type: EvaluationSummarySerializer(s).data
                    for s in summaries
                },
            }
        )


class GreenhouseControlProfileView(APIView):
    """GET/PATCH AMPC control profile for one owned greenhouse."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, greenhouse_id: int) -> Response:
        try:
            profile = get_owned_profile(user=request.user, greenhouse_id=greenhouse_id)
        except AMPCNotFound:
            raise Http404
        data = GreenhouseControlProfileSerializer(profile).data
        return Response(_success(data))

    def patch(self, request: Request, greenhouse_id: int) -> Response:
        try:
            profile = get_owned_profile(user=request.user, greenhouse_id=greenhouse_id)
        except AMPCNotFound:
            raise Http404
        serializer = GreenhouseControlProfileSerializer(
            profile,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return _error_response(
                "invalid_profile",
                "Control profile validation failed.",
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )
        serializer.save()
        return Response(_success(GreenhouseControlProfileSerializer(profile).data))


class AMPCRecommendationCreateView(APIView):
    """Run AMPC for an owned greenhouse and persist the recommendation."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, greenhouse_id: int) -> Response:
        if request.data not in ({}, None):
            return _error_response(
                "invalid_body",
                "AMPC recommendation endpoint does not accept request parameters.",
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            rec = run_ampc_for_greenhouse(
                user=request.user,
                greenhouse_id=greenhouse_id,
            )
        except AMPCNotFound:
            raise Http404
        except AMPCForbidden as exc:
            return _error_response(
                str(exc),
                "Greenhouse cannot run AMPC.",
                status.HTTP_403_FORBIDDEN,
            )
        return Response(
            _success(AMPCRecommendationSerializer(rec).data),
            status=status.HTTP_201_CREATED,
        )


class AMPCLatestRecommendationView(APIView):
    """Return latest AMPC recommendation for one owned greenhouse."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, greenhouse_id: int) -> Response:
        try:
            rec = latest_recommendation_for_user(
                user=request.user,
                greenhouse_id=greenhouse_id,
            )
        except AMPCNotFound:
            raise Http404
        if rec is None:
            return _error_response(
                "recommendation_not_found",
                "No AMPC recommendation exists for this greenhouse.",
                status.HTTP_404_NOT_FOUND,
            )
        return Response(_success(AMPCRecommendationSerializer(rec).data))


def _success(data: object) -> dict[str, object]:
    return {"success": True, "data": data, "error": None}


def _error_response(
    code: str,
    message: str,
    response_status: int,
    *,
    details: object | None = None,
) -> Response:
    return Response(
        {
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "trace_id": get_random_string(12),
            },
        },
        status=response_status,
    )
