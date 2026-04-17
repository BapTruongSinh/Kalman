"""
Endpoint nạp dữ liệu sensor live

Endpoint
--------
"POST /api/ingest/samples/"

Nhận một sample sensor, chạy qua cùng pipeline validate/tiền xử lý như replay
CSV offline, chạy một bước Kalman, lưu dòng "PipelineCycle" và trả về giá trị
ước lượng sau lọc.

Ghi chú thiết kế
----------------
Xác thực
    Dùng DRF "TokenAuthentication". Endpoint này luôn cần token.
    Các API "GET" chỉ đọc cho dashboard đi theo "DASHBOARD_REQUIRE_AUTH" /
    "DEFAULT_PERMISSION_CLASSES" trong Django settings; production mặc định
    yêu cầu user đã xác thực, trừ khi mở rõ ràng.

    Provision a token::

        python manage.py drf_create_token <username>

    Then include the header "Authorization: Token <key>" in every POST.

An toàn khi reconnect
    Trạng thái Kalman (x_post, P_post, R) được load từ "PipelineCycle" *đã lưu
    gần nhất* ở mỗi request. Thiết bị có thể mất kết nối rồi reconnect; bộ lọc
    sẽ chạy tiếp từ điểm đã dừng.

Xử lý khoảng trống thời gian
    Chấp nhận gap timestamp do thiết bị tắt hoặc mất sample. Model Kalman hiện
    tại không biến thiên theo thời gian (Q cố định), nên gap được xử lý như một
    bước bình thường, không cần xử lý đặc biệt.

Dự đoán ARX
    Đường live ở v1 cố ý chưa dùng ARX. Train ARX cần batch dữ liệu offline;
    adapter để "None" nên prior Kalman fallback về posterior trước đó. Sau này
    có thể nối artifact ARX đã train khi có dataset từ thiết bị live.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..ingestion.loader import RawRecord
from ..ingestion.preprocessor import preprocess_single
from ..ingestion.validator import DEFAULT_CONFIG as DEFAULT_VALIDATION_CONFIG
from ..ingestion.validator import validate_live_record
from ..kalman import AdaptiveKalmanCycle
from ..kalman.cycle import KalmanConfig, KalmanState
from ..models import ExperimentConfig, ExperimentRun, PipelineCycle
from ..pipeline.store import ingest_dedupe_key_for_persist, map_result_to_cycle
from .live_serializers import LiveSampleSerializer

logger = logging.getLogger(__name__)

_SENSOR_FIELDS = (
    "soil_moisture",
    "temperature",
    "humidity",
    "light",
    "drip",
    "mist",
    "fan",
)


# ── Helper ────────────────────────────────────────────────────────────────────


def _kalman_config_from_db(exp_config: ExperimentConfig) -> KalmanConfig:
    """Tạo :class:`~..kalman.cycle.KalmanConfig` từ snapshot đã lưu."""
    return KalmanConfig(
        x0=exp_config.x0,
        P0=exp_config.P0,
        Q=exp_config.Q,
        R0=exp_config.R0,
        R_min=exp_config.R_min,
        R_max=exp_config.R_max,
        alpha=exp_config.alpha,
    )


def _restore_state(
    last_cycle: PipelineCycle | None,
    config: KalmanConfig,
) -> tuple[KalmanState, int]:
    """Dựng lại state của bộ lọc và "cycle_index" kế tiếp từ DB.
    """
    if last_cycle is None:
        return KalmanState.from_config(config), 0

    next_index = last_cycle.cycle_index + 1
    x_post = last_cycle.kf_x_posterior
    p_post = last_cycle.kf_P_posterior
    r_val = last_cycle.kf_R

    if (
        x_post is None
        or p_post is None
        or r_val is None
        or p_post <= 0.0
        or r_val <= 0.0
    ):
        logger.warning(
            "Live run %d: last cycle %d has incomplete Kalman fields "
            "(x=%s P=%s R=%s); resetting state from config.",
            last_cycle.run_id,
            last_cycle.cycle_index,
            x_post,
            p_post,
            r_val,
        )
        return KalmanState.from_config(config), next_index

    return (
        KalmanState(x_post=x_post, P_post=p_post, R=r_val, step=next_index),
        next_index,
    )


def _normalize_sample_ts(ts: datetime) -> datetime:
    """Trả *ts* dạng timezone-aware UTC; timestamp naïve được xem là UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _live_ingest_response_body(
    *,
    cycle_index: int,
    preprocess_status: str,
    cycle_status: str,
    adaptive_status: str,
    kf_x_posterior: float | None,
    kf_innovation: float | None,
    idempotent: bool = False,
) -> dict:
    """Body JSON cho live ingest thành công, gồm 201 hoặc idempotent 200."""
    body: dict = {
        "cycle_index": cycle_index,
        "preprocess_status": preprocess_status,
        "cycle_status": cycle_status,
        "adaptive_status": adaptive_status,
        "kf_x_posterior": kf_x_posterior,
        "kf_innovation": kf_innovation,
    }
    if idempotent:
        body["idempotent"] = True
    return body


def _response_from_pipeline_cycle(
    cycle: PipelineCycle, *, idempotent: bool = False
) -> dict:
    """Tạo body JSON public từ :class:`~..models.PipelineCycle` đã lưu."""
    return _live_ingest_response_body(
        cycle_index=cycle.cycle_index,
        preprocess_status=cycle.preprocess_status,
        cycle_status=cycle.cycle_status,
        adaptive_status=cycle.adaptive_status,
        kf_x_posterior=cycle.kf_x_posterior,
        kf_innovation=cycle.kf_innovation,
        idempotent=idempotent,
    )


def _nullable_float_equal(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return float(a) == float(b)


def _live_sensor_payload_matches(data: dict, cycle: PipelineCycle) -> bool:
    """True nếu request *data* đã validate khớp các cột "raw_*" trên *cycle*."""
    for field in _SENSOR_FIELDS:
        if not _nullable_float_equal(data.get(field), getattr(cycle, f"raw_{field}")):
            return False
    return True


def _build_raw_record(data: dict, row_index: int) -> RawRecord:
    """Đổi dữ liệu serializer đã validate thành :class:`~..ingestion.loader.RawRecord`.

    Nếu timestamp gửi lên là naïve thì chuyển thành UTC-aware.
    """
    ts = _normalize_sample_ts(data["timestamp"])
    return RawRecord(
        timestamp=ts,
        soil_moisture=data.get("soil_moisture"),
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        light=data.get("light"),
        drip=data.get("drip"),
        mist=data.get("mist"),
        fan=data.get("fan"),
        row_index=row_index,
    )


# ── View ──────────────────────────────────────────────────────────────────────


class LiveIngestView(APIView):
    """Nhận một sample sensor live và chạy một bước Kalman.

    **Xác thực**: bắt buộc có header "Authorization: Token <key>".

    **Request body** (JSON):

    .. code-block:: json

        {
            "run_id": 42,
            "timestamp": "2026-04-14T12:00:00Z",
            "soil_moisture": 45.3,
            "temperature": 22.1,
            "humidity": 65.0,
            "light": 120.0,
            "drip": 0.0,
            "mist": 0.0,
            "fan": 1.0
        }

    Tất cả kênh sensor trừ "timestamp" và "run_id" đều tùy chọn và nhận
    "null".

    **Response**:

    * "201 Created": sample được nhận; body chứa estimate sau lọc.
    * "200 OK": cùng "run_id" + "timestamp" và payload sensor giống hệt đã
      ingest trước đó; body là cycle đã có (""idempotent": true"), an toàn cho retry.
    * "400 Bad Request": payload sai, thiếu field bắt buộc hoặc sai kiểu.
    * "401 Unauthorized": thiếu token hoặc token không hợp lệ.
    * "403 Forbidden": user xác thực không phải "owner" của run, hoặc live
      run chưa gán "owner" nên tạm khóa ingest.
    * "404 Not Found": "run_id" không tồn tại hoặc không phải live run.
    * "409 Conflict": run không ở ""running"", hoặc cùng "timestamp" đã
      ingest với payload sensor **khác** nên không được ghi đè.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:  # noqa: PLR0911
        # ── Deserialize và validate payload ──────────────────────────────────
        serializer = LiveSampleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        run_id: int = data["run_id"]

        # ── Pre-check nhanh: loại run_id sai rõ ràng trước khi lock ──────────
        # Đây chỉ là guard; check có thẩm quyền về type và status nằm
        # trong atomic block, nơi row đã được lock.
        if not ExperimentRun.objects.filter(
            pk=run_id, run_type=ExperimentRun.RunType.LIVE
        ).exists():
            return Response(
                {"error": f"Live ExperimentRun id={run_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Atomic: lock run, check state, dựng state, step, rồi lưu ─────────
        # MỌI guard nhạy với state (run_type, status) được kiểm tra *sau khi*
        # lấy row lock, để chuyển trạng thái đồng thời (running → completed)
        # không lọt qua giữa pre-check và lúc ghi. Cách này loại race TOCTOU.
        #
        # Unique constraint trên (run, cycle_index) cũng được bảo vệ bởi cùng
        # lock: tại một thời điểm chỉ một request cho mỗi run được tính và lưu
        # cycle_index mới.
        with transaction.atomic():
            # Lock và eager-load config trong một query.
            try:
                run = ExperimentRun.objects.select_for_update().select_related(
                    "config"
                ).get(pk=run_id, run_type=ExperimentRun.RunType.LIVE)
            except ExperimentRun.DoesNotExist:
                return Response(
                    {"error": f"Live ExperimentRun id={run_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Phân quyền cấp object: chỉ owner đã gán mới được ingest.
            if run.owner_id is None:
                return Response(
                    {
                        "error": (
                            "This live run has no owner assigned; ingestion is "
                            "disabled until owner is set on the ExperimentRun."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if run.owner_id != request.user.pk:
                return Response(
                    {
                        "error": (
                            "You do not have permission to ingest samples for "
                            "this run."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Guard trạng thái có thẩm quyền, chạy khi vẫn đang giữ row lock.
            if run.status != ExperimentRun.Status.RUNNING:
                return Response(
                    {
                        "error": (
                            f"Run {run_id} is '{run.status}', not 'running'. "
                            "Transition the run to 'running' before sending samples."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # Load Kalman config từ relation đã fetch, không cần query thêm.
            try:
                kalman_config = _kalman_config_from_db(run.config)
            except ExperimentConfig.DoesNotExist:
                logger.warning(
                    "Live run %d has no ExperimentConfig; using ADR-003 defaults.",
                    run_id,
                )
                kalman_config = KalmanConfig()

            sample_ts = _normalize_sample_ts(data["timestamp"])
            dedupe_key = ingest_dedupe_key_for_persist(
                run.pk,
                PipelineCycle.SourceType.LIVE,
                cycle_index=0,
                sample_ts=sample_ts,
            )
            existing_live = PipelineCycle.objects.filter(
                run=run,
                ingest_dedupe_key=dedupe_key,
            ).first()
            if existing_live is not None:
                if _live_sensor_payload_matches(data, existing_live):
                    return Response(
                        _response_from_pipeline_cycle(existing_live, idempotent=True),
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {
                        "error": (
                            "A sample with this timestamp was already ingested "
                            "with different sensor values; refusing to overwrite."
                        ),
                        "code": "duplicate_timestamp_payload_mismatch",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            last_cycle: PipelineCycle | None = (
                PipelineCycle.objects.filter(run=run).order_by("-cycle_index").first()
            )
            state, cycle_index = _restore_state(last_cycle, kalman_config)

            # Tạo raw record với cycle_index đã biết.
            raw_record = _build_raw_record(data, row_index=cycle_index)

            # Dùng validate_live_record: với live ingest, các field phụ là tùy
            # chọn; chỉ field nào thật sự có mặt mới bị kiểm tra range.
            # soil_moisture=None → is_valid=False (missing) → preprocess_status="skipped".
            # soil_moisture có mặt và trong range → is_valid=True → preprocess_status="valid".
            validation = validate_live_record(raw_record, config=DEFAULT_VALIDATION_CONFIG)
            processed = preprocess_single(raw_record, validation)

            estimator = AdaptiveKalmanCycle(kalman_config)
            estimator._state = state  # inject state đã dựng lại từ DB
            cycle_result = estimator.step(processed, cycle_index=cycle_index)

            cycle_obj = map_result_to_cycle(
                cycle_result,
                run,
                slice_type=PipelineCycle.SliceType.TRAIN,
                source_type=PipelineCycle.SourceType.LIVE,
                record=processed,
            )
            try:
                with transaction.atomic():
                    cycle_obj.save()
            except IntegrityError:
                # Race hiếm: worker khác đã insert cùng dedupe key trước.
                dup = PipelineCycle.objects.filter(
                    run=run,
                    ingest_dedupe_key=dedupe_key,
                ).first()
                if dup is None:
                    raise
                if _live_sensor_payload_matches(data, dup):
                    return Response(
                        _response_from_pipeline_cycle(dup, idempotent=True),
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {
                        "error": (
                            "A sample with this timestamp was already ingested "
                            "with different sensor values; refusing to overwrite."
                        ),
                        "code": "duplicate_timestamp_payload_mismatch",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        logger.info(
            "Live run %d: cycle %d persisted (status=%s, adaptive=%s).",
            run_id,
            cycle_index,
            cycle_result.cycle_status,
            cycle_result.adaptive_status,
        )

        return Response(
            _live_ingest_response_body(
                cycle_index=cycle_index,
                preprocess_status=processed.preprocess_status,
                cycle_status=cycle_result.cycle_status,
                adaptive_status=cycle_result.adaptive_status,
                kf_x_posterior=cycle_result.x_posterior,
                kf_innovation=cycle_result.innovation,
            ),
            status=status.HTTP_201_CREATED,
        )
