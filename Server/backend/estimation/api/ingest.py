"""Live sensor ingest endpoint.

Endpoint
--------
``POST /api/ingest/samples/``

Receives one sensor sample, validates/preprocesses it, runs one Adaptive Kalman
step, stores a ``PipelineCycle``, and returns the filtered estimate.

Design notes
------------
Authentication
    Uses DRF ``TokenAuthentication`` and always requires an authenticated user.
    Read-only dashboard APIs follow ``DASHBOARD_REQUIRE_AUTH`` /
    ``DEFAULT_PERMISSION_CLASSES`` in Django settings.

Reconnect safety
    Kalman state (x_post, P_post, R) is loaded from the latest persisted
    ``PipelineCycle`` on every request so devices can reconnect safely.

Timestamp gaps
    Timestamp gaps are accepted. The current scalar Kalman model uses fixed
    process noise, so gaps are treated as normal discrete steps.

ARX prediction
    The live runtime loads a cached ``ARXPredictionAdapter`` from
    ``settings.ARX_MODEL_PATH`` and reconstructs minimal per-run history from
    previous live cycles. If the artifact is missing/invalid, ingest continues
    with the carry-forward Kalman prior and logs an internal warning.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from kalman.filter import AdaptiveKalmanCycle, KalmanConfig, KalmanState
from kalman.ingestion import ProcessedRecord, RawRecord, ValidationResult, preprocess_single
from kalman.ingestion.validator import DEFAULT_CONFIG as DEFAULT_VALIDATION_CONFIG
from kalman.ingestion.validator import validate_live_record
from kalman.prediction import ARXPredictionAdapter, PredictionAdapter

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


@lru_cache(maxsize=1)
def _load_live_arx_adapter() -> PredictionAdapter | None:
    """Load cached ARX adapter for online runtime; never raises to request path."""
    artifact_path = Path(settings.ARX_MODEL_PATH)
    try:
        adapter = ARXPredictionAdapter.load_artifact(artifact_path)
    except FileNotFoundError:
        logger.warning("Live ARX artifact not found; using carry-forward prior.")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Live ARX artifact could not be loaded: %s", exc)
        return None
    logger.info("Loaded live ARX artifact from configured model path.")
    return adapter


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
    """Dựng lại state của bộ lọc và ``cycle_index`` kế tiếp từ DB.

    Parameters
    ----------
    last_cycle:
        :class:`~..models.PipelineCycle` mới nhất của run, hoặc ``None`` nếu
        chưa lưu cycle nào.
    config:
        :class:`~..kalman.cycle.KalmanConfig` đang dùng cho run.

    Returns
    -------
    (state, cycle_index)
        *state* sẽ được inject vào estimator trước khi gọi ``step()``.
        *cycle_index* là index bắt đầu từ 0 cho bước mới này.

    Ghi chú
    -------
    Nếu cycle cuối có ``None`` ở bất kỳ field Kalman nào, ví dụ sau cycle lỗi,
    state được reset từ *config*. Như vậy reconnect vẫn sạch kể cả sau bước lỗi.
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
    """True nếu request *data* đã validate khớp các cột ``raw_*`` trên *cycle*."""
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


def _processed_record_from_cycle(cycle: PipelineCycle) -> ProcessedRecord:
    """Rebuild a minimal ProcessedRecord from a persisted live cycle."""
    raw = RawRecord(
        timestamp=_normalize_sample_ts(cycle.sample_ts),
        soil_moisture=cycle.raw_soil_moisture,
        temperature=cycle.raw_temperature,
        humidity=cycle.raw_humidity,
        light=cycle.raw_light,
        drip=cycle.raw_drip,
        mist=cycle.raw_mist,
        fan=cycle.raw_fan,
        row_index=cycle.cycle_index,
    )
    is_valid = cycle.preprocess_status == PipelineCycle.PreprocessStatus.VALID
    validation = ValidationResult(
        is_valid=is_valid,
        status="valid" if is_valid else "skipped",
    )
    if is_valid:
        return ProcessedRecord(
            raw=raw,
            validation=validation,
            preprocess_status=cycle.preprocess_status,
            soil_moisture=cycle.raw_soil_moisture,
            temperature=cycle.raw_temperature,
            humidity=cycle.raw_humidity,
            light=cycle.raw_light,
            drip=cycle.raw_drip,
            mist=cycle.raw_mist,
            fan=cycle.raw_fan,
        )
    return ProcessedRecord(
        raw=raw,
        validation=validation,
        preprocess_status="skipped",
        soil_moisture=None,
        temperature=None,
        humidity=None,
        light=None,
        drip=None,
        mist=None,
        fan=None,
    )


def _live_history_for_adapter(
    run: ExperimentRun,
    adapter: PredictionAdapter | None,
) -> list[ProcessedRecord]:
    """Load only the previous live cycles needed for a causal ARX prediction."""
    if adapter is None:
        return []
    min_history = max(0, getattr(adapter, "min_history_len", 0))
    if min_history <= 0:
        return []

    cycles = list(
        PipelineCycle.objects.filter(
            run=run,
            source_type=PipelineCycle.SourceType.LIVE,
        )
        .order_by("-cycle_index")[:min_history]
    )
    cycles.reverse()
    return [_processed_record_from_cycle(cycle) for cycle in cycles]


# ── View ──────────────────────────────────────────────────────────────────────


class LiveIngestView(APIView):
    """Nhận một sample sensor live và chạy một bước Kalman.

    **Xác thực**: bắt buộc có header ``Authorization: Token <key>``.

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

    Tất cả kênh sensor trừ ``timestamp`` và ``run_id`` đều tùy chọn và nhận
    ``null``.

    **Response**:

    * ``201 Created``: sample được nhận; body chứa estimate sau lọc.
    * ``200 OK``: cùng ``run_id`` + ``timestamp`` và payload sensor giống hệt đã
      ingest trước đó; body là cycle đã có (``"idempotent": true``), an toàn cho retry.
    * ``400 Bad Request``: payload sai, thiếu field bắt buộc hoặc sai kiểu.
    * ``401 Unauthorized``: thiếu token hoặc token không hợp lệ.
    * ``403 Forbidden``: authenticated user is not the greenhouse owner, or the
      greenhouse is inactive.
    * ``404 Not Found``: ``run_id`` không tồn tại hoặc không phải live run.
    * ``409 Conflict``: run không ở ``"running"``, hoặc cùng ``timestamp`` đã
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
        # Đây chỉ là guard lạc quan; check có thẩm quyền về type và status nằm
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
                    "config",
                    "greenhouse",
                    "greenhouse__owner",
                ).get(pk=run_id, run_type=ExperimentRun.RunType.LIVE)
            except ExperimentRun.DoesNotExist:
                return Response(
                    {"error": f"Live ExperimentRun id={run_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Object-level auth: token user must own the greenhouse.
            if not run.greenhouse.is_active:
                return Response(
                    {
                        "error": (
                            "This greenhouse is inactive; ingestion is disabled "
                            "until the greenhouse is reactivated."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if run.greenhouse.owner_id != request.user.pk:
                return Response(
                    {
                        "error": (
                            "You do not have permission to ingest samples for "
                            "this greenhouse."
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

            adapter = _load_live_arx_adapter()
            estimator = AdaptiveKalmanCycle(kalman_config, adapter=adapter)
            estimator._state = state  # inject state đã dựng lại từ DB
            estimator._history = _live_history_for_adapter(run, adapter)
            cycle_result = estimator.step(processed, cycle_index=cycle_index)

            cycle_obj = map_result_to_cycle(
                cycle_result,
                run,
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
