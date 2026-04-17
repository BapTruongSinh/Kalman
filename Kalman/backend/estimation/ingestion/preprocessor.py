"""
Các chính sách tiền xử lý dữ liệu sensor greenhouse.

Sau bước validation, mỗi record không hợp lệ phải được xử lý bằng một trong
ba policy trước khi đi vào estimation pipeline:

keep_last
    Thay TẤT CẢ field của record lỗi bằng giá trị hợp lệ gần nhất.
    Áp dụng cho cả field thiếu (None) và field có giá trị vượt ngưỡng.
    Kết quả có ``preprocess_status="kept_last"``.

interpolate
    Nội suy tuyến tính giữa giá trị hợp lệ trước đó và giá trị hợp lệ kế tiếp
    cho mọi field của record lỗi. Nếu không có giá trị kế tiếp thì fallback
    về keep_last. Kết quả có ``preprocess_status="interpolated"``.

skip
    Set tất cả effective field thành ``None`` cho record lỗi.
    ``preprocess_status="skipped"``. Kalman cycle sẽ bỏ qua bước measurement
    update khi measurement là None.

Record có ``ValidationResult.status`` là ``"valid"`` sẽ đi qua không đổi với
``preprocess_status="valid"``.

Ghi chú: giá trị ``preprocess_status`` phải khớp choices trong
``estimation.models.PipelineCycle.PreprocessStatus``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from .loader import RawRecord
from .validator import ValidationResult

logger = logging.getLogger(__name__)

# Các field số có thể tiền xử lý.
_FIELDS = ("soil_moisture", "temperature", "humidity", "light", "drip", "mist", "fan")

# Tên policy phải khớp ExperimentConfig.PreprocessPolicy.
KEEP_LAST = "keep_last"
INTERPOLATE = "interpolate"
SKIP = "skip"

VALID_POLICIES = (KEEP_LAST, INTERPOLATE, SKIP)


# Processed record.

@dataclass(frozen=True)
class ProcessedRecord:
    """Record sau khi đã áp dụng preprocessing.

    ``raw`` và ``validation`` được giữ lại để truy vết đầy đủ.
    Các field số là effective value sẽ đưa vào estimation pipeline; chúng có
    thể là ``None`` khi policy là ``skip`` hoặc không thể thay thế giá trị.
    """

    raw: RawRecord
    validation: ValidationResult
    preprocess_status: str  # valid | kept_last | interpolated | skipped

    # Giá trị thực tế sau preprocessing.
    soil_moisture: float | None
    temperature: float | None
    humidity: float | None
    light: float | None
    drip: float | None
    mist: float | None
    fan: float | None


# Public API.

def apply_preprocessing(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
    policy: str = KEEP_LAST,
) -> list[ProcessedRecord]:
    """Áp dụng preprocessing policy cho toàn bộ sequence records.

    Tham số
    -------
    records:
        Raw records theo thứ tự thời gian.
    validations:
        Một :class:`~validator.ValidationResult` cho mỗi record, cùng thứ tự.
    policy:
        Một trong ``"keep_last"``, ``"interpolate"``, hoặc ``"skip"``.

    Trả về
    ------
    list[ProcessedRecord]
        Một processed record cho mỗi input record.

    Lỗi
    ---
    ValueError
        Nếu ``records`` và ``validations`` khác độ dài, hoặc policy không hợp lệ.
    """
    if len(records) != len(validations):
        raise ValueError(
            f"records ({len(records)}) and validations ({len(validations)}) "
            "must have the same length"
        )
    if policy not in VALID_POLICIES:
        raise ValueError(
            f"Unknown policy {policy!r}. Expected one of {VALID_POLICIES}"
        )

    if policy == KEEP_LAST:
        return _apply_keep_last(records, validations)
    if policy == INTERPOLATE:
        return _apply_interpolate(records, validations)
    return _apply_skip(records, validations)


# Implement từng policy.

def _apply_keep_last(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
) -> list[ProcessedRecord]:
    """Keep-last-valid: thay mọi field của record lỗi.

    Khi record fail validation, dù vì field None hay vượt ngưỡng, tất cả
    effective field sẽ được thay bằng measurement hợp lệ gần nhất.
    """
    last_valid: dict[str, float | None] = {f: None for f in _FIELDS}
    result: list[ProcessedRecord] = []

    for record, vr in zip(records, validations):
        if vr.is_valid:
            # Cập nhật giá trị hợp lệ gần nhất và giữ record nguyên trạng.
            for f in _FIELDS:
                val = getattr(record, f)
                if val is not None:
                    last_valid[f] = val
            result.append(_make_processed(record, vr, "valid", last_valid))
        else:
            # Record lỗi: thay TẤT CẢ field bằng giá trị hợp lệ gần nhất.
            # Kể cả giá trị out_of_range không None cũng không được đưa xuống dưới.
            effective = {f: last_valid[f] for f in _FIELDS}
            result.append(_make_processed(record, vr, "kept_last", effective))

    return result


def _apply_interpolate(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
) -> list[ProcessedRecord]:
    """Nội suy tuyến tính giữa các giá trị hợp lệ lân cận.

    Với mỗi record lỗi, mọi field được nội suy giữa giá trị hợp lệ trước và
    sau. Giá trị vượt ngưỡng bị loại bỏ như missing value. Nếu không có giá trị
    hợp lệ kế tiếp thì fallback về keep_last.
    """
    n = len(records)

    # Tính trước index của giá trị hợp lệ kế tiếp theo từng field.
    next_valid_idx: dict[str, list[int | None]] = {f: [None] * n for f in _FIELDS}
    for f in _FIELDS:
        nv: int | None = None
        for i in range(n - 1, -1, -1):
            if validations[i].is_valid and getattr(records[i], f) is not None:
                nv = i
            next_valid_idx[f][i] = nv

    last_valid_val: dict[str, float | None] = {f: None for f in _FIELDS}
    # Lưu index của giá trị hợp lệ gần nhất để tính khoảng nội suy.
    last_valid_idx: dict[str, int] = {f: -1 for f in _FIELDS}
    result: list[ProcessedRecord] = []

    for i, (record, vr) in enumerate(zip(records, validations)):
        if vr.is_valid:
            for f in _FIELDS:
                val = getattr(record, f)
                if val is not None:
                    last_valid_val[f] = val
                    last_valid_idx[f] = i
            result.append(_make_processed(record, vr, "valid", last_valid_val))
            continue

        # Record lỗi: nội suy TẤT CẢ field, không tin raw value nữa.
        effective: dict[str, float | None] = {}
        for f in _FIELDS:
            lv = last_valid_val[f]
            nv_idx = next_valid_idx[f][i]

            if lv is None and nv_idx is None:
                # Không có dữ liệu hai phía thì giữ None.
                effective[f] = None
            elif lv is None:
                # Không có giá trị trước đó thì mượn giá trị hợp lệ kế tiếp.
                effective[f] = getattr(records[nv_idx], f)  # type: ignore[index]
            elif nv_idx is None:
                # Không có giá trị kế tiếp thì fallback về last valid.
                effective[f] = lv
            else:
                nv = getattr(records[nv_idx], f)
                if nv is None:
                    effective[f] = lv
                else:
                    lv_i = last_valid_idx[f]
                    gap = nv_idx - lv_i
                    pos = i - lv_i
                    effective[f] = lv + (nv - lv) * (pos / gap) if gap > 0 else lv

        result.append(_make_processed(record, vr, "interpolated", effective))

    return result


def _apply_skip(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
) -> list[ProcessedRecord]:
    """Giữ record hợp lệ; set toàn bộ effective value thành None nếu record lỗi.

    Record skipped trả ``None`` cho mọi field để Kalman cycle nhận biết và bỏ
    measurement-update. Giá trị raw vượt ngưỡng bị chuyển thành None.
    """
    result: list[ProcessedRecord] = []
    for record, vr in zip(records, validations):
        if vr.is_valid:
            effective = {f: getattr(record, f) for f in _FIELDS}
            result.append(_make_processed(record, vr, "valid", effective))
        else:
            # Skipped: trả None cho mọi field, bất kể raw value là gì.
            effective = {f: None for f in _FIELDS}
            result.append(_make_processed(record, vr, "skipped", effective))
    return result


# Helpers.

def _make_processed(
    record: RawRecord,
    vr: ValidationResult,
    status: str,
    effective: dict[str, float | None],
) -> ProcessedRecord:
    return ProcessedRecord(
        raw=record,
        validation=vr,
        preprocess_status=status,
        soil_moisture=effective.get("soil_moisture"),
        temperature=effective.get("temperature"),
        humidity=effective.get("humidity"),
        light=effective.get("light"),
        drip=effective.get("drip"),
        mist=effective.get("mist"),
        fan=effective.get("fan"),
    )


def preprocess_single(
    record: RawRecord,
    validation: ValidationResult,
) -> ProcessedRecord:
    """Tạo :class:`ProcessedRecord` cho một record bằng skip policy.

    Đây là policy phù hợp cho live sensor ingestion: nếu reading không hợp lệ
    thì không có context tương lai để nội suy, nên toàn bộ effective field được
    set None và Kalman cycle bỏ measurement-update.

    Tham số
    -------
    record:
        Raw sensor record, tức một sample từ thiết bị.
    validation:
        Kết quả validate record.

    Trả về
    ------
    ProcessedRecord
        ``preprocess_status="valid"`` nếu reading pass validation; ngược lại
        là ``preprocess_status="skipped"`` với effective value toàn None.
    """
    if validation.is_valid:
        effective: dict[str, float | None] = {f: getattr(record, f) for f in _FIELDS}
        return _make_processed(record, validation, "valid", effective)
    effective = {f: None for f in _FIELDS}
    return _make_processed(record, validation, "skipped", effective)
