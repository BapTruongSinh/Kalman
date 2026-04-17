"""
Tầng lưu trữ pipeline (Task #007).

Trách nhiệm
-----------
* Map ``CycleResult`` thành một instance ORM ``PipelineCycle`` chưa lưu, gồm
  cả việc đổi tên sang các cột tiền tố ``kf_`` và copy cột sensor thô từ
  ``ProcessedRecord`` tương ứng nếu có.
* Bulk-insert các batch ``PipelineCycle`` hiệu quả.
* Chuyển trạng thái ``ExperimentRun`` theo vòng đời:
  PENDING → RUNNING → COMPLETED | FAILED | ABORTED.

Ràng buộc thiết kế
------------------
* ``map_result_to_cycle`` là **pure function**, không gọi DB. Tất cả logic đổi
  field nằm ở đây để đường bulk-insert chỉ lo ghi dữ liệu.
* ``bulk_save_cycles`` gọi một ``bulk_create`` theo batch, không INSERT từng dòng.
* Chuyển trạng thái dùng ``QuerySet.update`` có điều kiện, tức một câu UPDATE,
  để tránh race condition; nếu pre-condition không đúng thì raise
  ``RunStateError``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from ..ingestion.preprocessor import ProcessedRecord
from ..kalman import CycleResult
from ..models import ExperimentRun, PipelineCycle

logger = logging.getLogger(__name__)


# ── Helper ────────────────────────────────────────────────────────────────────


def ingest_dedupe_key_for_persist(
    run_id: int,
    source_type: str,
    *,
    cycle_index: int,
    sample_ts: datetime | None = None,
) -> str:
    """Tạo khóa unique an toàn cho MySQL cho ``PipelineCycle.ingest_dedupe_key``.

    Một số cấu hình MySQL không tạo được partial ``UNIQUE`` index kiểu
    ``WHERE source_type='live'``, nên hệ thống dùng key string tường minh.

    * **live**: ``live|{run_id}|{UTC ISO-8601 timestamp}``, tối đa một dòng live
      cho mỗi run và mỗi timestamp sensor, giúp retry không ghi trùng.
    * **csv_replay / mysql_replay**: ``csv|...`` / ``mysql|...`` cộng
      ``cycle_index`` pad số 0, vì các dòng CSV có thể trùng ``sample_ts``.
    """
    if source_type == PipelineCycle.SourceType.LIVE:
        if sample_ts is None:
            raise ValueError("ingest_dedupe_key_for_persist: sample_ts required for live")
        ts = sample_ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        return f"live|{run_id}|{ts.isoformat()}"
    if source_type == PipelineCycle.SourceType.CSV_REPLAY:
        return f"csv|{run_id}|{cycle_index:010d}"
    if source_type == PipelineCycle.SourceType.MYSQL_REPLAY:
        return f"mysql|{run_id}|{cycle_index:010d}"
    raise ValueError(f"unsupported source_type {source_type!r}")


def _require_choice(value: str, choices: type, field: str) -> str:
    """Validate *value* theo một class TextChoices; sai thì raise ``ValueError``.

    Đây là lớp chặn ở boundary lưu trữ, để caller không thể âm thầm ghi enum rác
    vào bảng truy vết. Các ``CheckConstraint`` tương ứng trong model sẽ chặn
    thêm ở tầng DB.
    """
    valid = {v for v, _ in choices.choices}
    if value not in valid:
        raise ValueError(
            f"Invalid {field} value {value!r}. "
            f"Expected one of {sorted(valid)}."
        )
    return value


# ── Exception ─────────────────────────────────────────────────────────────────


class RunStateError(RuntimeError):
    """Raise khi chuyển trạng thái run không hợp lệ.

    Ví dụ: gọi ``begin_run`` trên run đã ``RUNNING``, hoặc gọi ``end_run`` trên
    run vẫn còn ``PENDING``.
    """


# ── Ánh xạ field ──────────────────────────────────────────────────────────────

# Các trạng thái kết thúc mà ``end_run`` chấp nhận.
_TERMINAL_STATUSES = frozenset({
    ExperimentRun.Status.COMPLETED,
    ExperimentRun.Status.FAILED,
    ExperimentRun.Status.ABORTED,
})


def map_result_to_cycle(
    result: CycleResult,
    run: ExperimentRun,
    slice_type: str,
    source_type: str = PipelineCycle.SourceType.CSV_REPLAY,
    record: ProcessedRecord | None = None,
) -> PipelineCycle:
    """Map ``CycleResult`` thành instance ORM ``PipelineCycle`` chưa lưu.

    Đây là **pure function**, không truy cập database. Muốn ghi DB thì dùng
    kèm :func:`bulk_save_cycles`.

    Ánh xạ field
    ------------
    CycleResult field        → PipelineCycle column
    ──────────────────────────────────────────────────
    timestamp                → sample_ts
    cycle_index              → cycle_index
    raw_soil_moisture        → raw_soil_moisture
    preprocess_status        → preprocess_status
    arx_predicted            → arx_predicted
    x_prior                  → kf_x_prior
    P_prior                  → kf_P_prior
    innovation               → kf_innovation
    R                        → kf_R
    K                        → kf_K
    x_posterior              → kf_x_posterior
    P_posterior              → kf_P_posterior
    adaptive_status          → adaptive_status
    cycle_status             → cycle_status
    error_message            → error_message
    latency_ms               → latency_ms

    Metadata cấp run do caller truyền vào:
    run, slice_type, source_type → PipelineCycle columns of the same name.

    Tất cả enum field (``slice_type``, ``source_type``, ``preprocess_status``,
    ``adaptive_status``, ``cycle_status``) được validate theo ``TextChoices``
    trước khi tạo instance. Giá trị lạ sẽ raise ``ValueError`` ngay, trước khi
    ghi DB.

    Parameters
    ----------
    result:
        Đầu ra của ``AdaptiveKalmanCycle.step()``.
    run:
        ``ExperimentRun`` cha, phải đã được lưu trong DB.
    slice_type:
        Một trong ``"train"``, ``"validation"``, ``"test"``.
    source_type:
        Một trong ``"csv_replay"``, ``"mysql_replay"``, ``"live"``; mặc định là
        ``"csv_replay"``.
    record:
        ``ProcessedRecord`` tùy chọn đã sinh ra result này. Nếu có, các giá trị
        sensor thô (temperature, humidity, light, drip, mist, fan) được copy
        sang các cột ``raw_*`` tương ứng để truy vết đầy đủ.
    """
    # ── Validate enum ở boundary lưu trữ ─────────────────────────────────────
    _require_choice(slice_type, PipelineCycle.SliceType, "slice_type")
    _require_choice(source_type, PipelineCycle.SourceType, "source_type")
    _require_choice(result.preprocess_status, PipelineCycle.PreprocessStatus, "preprocess_status")
    _require_choice(result.adaptive_status, PipelineCycle.AdaptiveStatus, "adaptive_status")
    _require_choice(result.cycle_status, PipelineCycle.CycleStatus, "cycle_status")

    raw = record.raw if record is not None else None

    dedupe_key = ingest_dedupe_key_for_persist(
        run.pk,
        source_type,
        cycle_index=result.cycle_index,
        sample_ts=result.timestamp,
    )

    return PipelineCycle(
        run=run,
        sample_ts=result.timestamp,
        cycle_index=result.cycle_index,
        ingest_dedupe_key=dedupe_key,
        slice_type=slice_type,
        source_type=source_type,
        # ── Đo lường thô ─────────────────────────────────────────────────────
        raw_soil_moisture=result.raw_soil_moisture,
        raw_temperature=raw.temperature if raw is not None else None,
        raw_humidity=raw.humidity if raw is not None else None,
        raw_light=raw.light if raw is not None else None,
        raw_drip=raw.drip if raw is not None else None,
        raw_mist=raw.mist if raw is not None else None,
        raw_fan=raw.fan if raw is not None else None,
        # ── Kết quả tiền xử lý ───────────────────────────────────────────────
        preprocess_status=result.preprocess_status,
        # ── Dự đoán ARX ──────────────────────────────────────────────────────
        arx_predicted=result.arx_predicted,
        # ── Giá trị nội bộ Kalman, dùng tiền tố kf_ theo schema ──────────────
        kf_x_prior=result.x_prior,
        kf_P_prior=result.P_prior,
        kf_innovation=result.innovation,
        kf_R=result.R,
        kf_K=result.K,
        kf_x_posterior=result.x_posterior,
        kf_P_posterior=result.P_posterior,
        # ── Kết quả của bộ ước lượng thích nghi ──────────────────────────────
        adaptive_status=result.adaptive_status,
        # ── Kết quả chu kỳ ───────────────────────────────────────────────────
        cycle_status=result.cycle_status,
        error_message=result.error_message,
        # ── Hiệu năng ────────────────────────────────────────────────────────
        latency_ms=result.latency_ms,
    )


# ── Ghi dữ liệu ───────────────────────────────────────────────────────────────


def bulk_save_cycles(
    cycles: Sequence[PipelineCycle],
    *,
    batch_size: int = 500,
) -> int:
    """Ghi một chuỗi instance ``PipelineCycle`` chưa lưu xuống DB.

    Dùng một lần gọi ``bulk_create`` theo *batch_size* để tăng throughput.
    Không gọi ``save()`` từng dòng trong vòng lặp nóng.

    Parameters
    ----------
    cycles:
        Các object ``PipelineCycle`` chưa lưu, thường được tạo bởi
        :func:`map_result_to_cycle`.
    batch_size:
        Số dòng mỗi câu INSERT, mặc định 500.

    Returns
    -------
    int
        Số dòng đã insert.
    """
    if not cycles:
        return 0
    created = PipelineCycle.objects.bulk_create(
        list(cycles),
        batch_size=batch_size,
    )
    n = len(created)
    logger.debug("bulk_save_cycles: inserted %d PipelineCycle rows", n)
    return n


# ── Vòng đời run ──────────────────────────────────────────────────────────────


def begin_run(run: ExperimentRun) -> None:
    """Chuyển *run* từ ``PENDING`` sang ``RUNNING``.

    Dùng ``QuerySet.update`` có điều kiện để thao tác chuyển trạng thái là
    atomic kể cả khi có truy cập đồng thời. Object *run* local được refresh từ
    database sau khi update thành công.

    Raises
    ------
    RunStateError
        If *run* is not currently ``PENDING`` (e.g. already ``RUNNING`` or
        ``COMPLETED``).
    """
    updated = ExperimentRun.objects.filter(
        pk=run.pk,
        status=ExperimentRun.Status.PENDING,
    ).update(
        status=ExperimentRun.Status.RUNNING,
        started_at=datetime.now(tz=timezone.utc),
    )
    if updated == 0:
        # Đọc lại trạng thái hiện tại để báo lỗi rõ hơn.
        current = ExperimentRun.objects.values_list("status", flat=True).get(pk=run.pk)
        raise RunStateError(
            f"Cannot begin run #{run.pk}: current status is {current!r}, "
            f"expected {ExperimentRun.Status.PENDING!r}."
        )
    run.refresh_from_db()
    logger.info("Run #%d started (status=running).", run.pk)


def end_run(run: ExperimentRun, status: str) -> None:
    """Chuyển *run* từ ``RUNNING`` sang trạng thái kết thúc.

    Các trạng thái kết thúc hợp lệ: ``"completed"``, ``"failed"``,
    ``"aborted"``. Object *run* local được refresh sau khi update thành công.

    Parameters
    ----------
    run:
        ``ExperimentRun`` cần kết thúc.
    status:
        Trạng thái kết thúc đích, phải là ``"completed"``, ``"failed"`` hoặc
        ``"aborted"``.

    Raises
    ------
    ValueError
        If *status* is not a recognised terminal status.
    RunStateError
        Nếu *run* hiện không phải ``RUNNING``.
    """
    if status not in _TERMINAL_STATUSES:
        raise ValueError(
            f"Invalid terminal status {status!r}. "
            f"Expected one of {sorted(_TERMINAL_STATUSES)}."
        )
    updated = ExperimentRun.objects.filter(
        pk=run.pk,
        status=ExperimentRun.Status.RUNNING,
    ).update(
        status=status,
        completed_at=datetime.now(tz=timezone.utc),
    )
    if updated == 0:
        current = ExperimentRun.objects.values_list("status", flat=True).get(pk=run.pk)
        raise RunStateError(
            f"Cannot end run #{run.pk}: current status is {current!r}, "
            f"expected {ExperimentRun.Status.RUNNING!r}."
        )
    run.refresh_from_db()
    logger.info("Run #%d ended (status=%s).", run.pk, status)
