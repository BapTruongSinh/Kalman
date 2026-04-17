"""
Validation theo từng record cho dữ liệu sensor greenhouse.

Validation gần như **stateless theo từng record**, ngoại trừ phát hiện
suspicious-repeat cần một cửa sổ nhỏ các giá trị trước đó. Caller không cần
repeat detection có thể truyền list rỗng cho ``prev_records``.

Nhóm kết quả validation
-----------------------
VALID
    Tất cả field có mặt và nằm trong ngưỡng vật lý hợp lý.
MISSING
    Một hoặc nhiều field số là ``None``. Trường hợp này bao gồm ô CSV rỗng,
    thiếu dữ liệu, hoặc chuỗi không parse được thành số.
OUT_OF_RANGE
    Field số có dữ liệu nhưng nằm ngoài ngưỡng vật lý đã cấu hình.
    NaN/Inf cũng được báo là ``out_of_range``.
SUSPICIOUS_REPEAT
    Biến chính Soil_Moisture không đổi trong ``repeat_threshold`` bước liên tiếp,
    có thể là sensor bị kẹt.

Ghi chú về timestamp lỗi
------------------------
Row có timestamp không parse được bị loader loại bỏ trước khi tạo ``RawRecord``.
Vì vậy validator này không nhận record thiếu timestamp và không cần category
MALFORMED riêng.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .loader import RawRecord


# Ngưỡng vật lý có thể cấu hình.

@dataclass(frozen=True)
class ValidationConfig:
    """Ngưỡng vật lý và cấu hình phát hiện sensor lặp.

    Tất cả ngưỡng là inclusive. Có thể chỉnh theo deployment nếu đặc tính
    sensor khác dataset greenhouse mặc định.
    """

    soil_moisture_min: float = 0.0
    soil_moisture_max: float = 100.0
    temperature_min: float = -10.0
    temperature_max: float = 60.0
    humidity_min: float = 0.0
    humidity_max: float = 100.0
    light_min: float = 0.0
    light_max: float = 150_000.0  # lux — full sunlight ≈ 100 000
    drip_min: float = 0.0
    drip_max: float = 1.0
    mist_min: float = 0.0
    mist_max: float = 1.0
    fan_min: float = 0.0
    fan_max: float = 1.0
    # Số lần Soil_Moisture giống hệt liên tiếp trước khi bị flag.
    repeat_threshold: int = 10


DEFAULT_CONFIG = ValidationConfig()


# Kiểu kết quả validation.

@dataclass(frozen=True)
class ValidationResult:
    """Kết quả validate một :class:`~loader.RawRecord`."""

    is_valid: bool
    status: str          # one of VALID | MISSING | OUT_OF_RANGE | SUSPICIOUS_REPEAT
    reason: str = ""     # giải thích dễ đọc khi record không hợp lệ


# Validator.

# Mapping field name -> (min, max) cho các field số cần kiểm tra.
_RANGE_CHECKS: tuple[tuple[str, str, str], ...] = (
    # (field_attr, config_min_attr, config_max_attr)
    ("soil_moisture", "soil_moisture_min", "soil_moisture_max"),
    ("temperature",   "temperature_min",   "temperature_max"),
    ("humidity",      "humidity_min",       "humidity_max"),
    ("light",         "light_min",          "light_max"),
    ("drip",          "drip_min",           "drip_max"),
    ("mist",          "mist_min",           "mist_max"),
    ("fan",           "fan_min",            "fan_max"),
)


def validate_record(
    record: RawRecord,
    prev_records: Sequence[RawRecord] | None = None,
    config: ValidationConfig = DEFAULT_CONFIG,
) -> ValidationResult:
    """Validate một record.

    Tham số
    -------
    record:
        Record cần validate.
    prev_records:
        Các record gần đây đứng trước record này. Chỉ dùng để phát hiện
        suspicious-repeat; có thể là ``None`` hoặc rỗng để bỏ qua check này.
    config:
        Ngưỡng vật lý và threshold. Mặc định là :data:`DEFAULT_CONFIG`.

    Trả về
    ------
    ValidationResult
        ``is_valid=True`` chỉ khi status là ``"valid"``.
    """
    # 1. Kiểm tra missing value.
    missing = [
        attr
        for attr, _, _ in _RANGE_CHECKS
        if getattr(record, attr) is None
    ]
    if missing:
        return ValidationResult(
            is_valid=False,
            status="missing",
            reason=f"None value(s) for: {', '.join(missing)}",
        )

    # 2. Chặn NaN / Inf.
    not_finite = [
        attr
        for attr, _, _ in _RANGE_CHECKS
        if not math.isfinite(getattr(record, attr))  # type: ignore[arg-type]
    ]
    if not_finite:
        return ValidationResult(
            is_valid=False,
            status="out_of_range",
            reason=f"Non-finite value(s) for: {', '.join(not_finite)}",
        )

    # 3. Kiểm tra ngưỡng vật lý.
    out_of_range = []
    for attr, min_attr, max_attr in _RANGE_CHECKS:
        val: float = getattr(record, attr)  # type: ignore[assignment]
        lo: float = getattr(config, min_attr)
        hi: float = getattr(config, max_attr)
        if not (lo <= val <= hi):
            out_of_range.append(
                f"{attr}={val:.4g} not in [{lo}, {hi}]"
            )
    if out_of_range:
        return ValidationResult(
            is_valid=False,
            status="out_of_range",
            reason="; ".join(out_of_range),
        )

    # 4. Kiểm tra suspicious-repeat, chỉ áp dụng cho Soil_Moisture.
    if prev_records and len(prev_records) >= config.repeat_threshold - 1:
        window = list(prev_records[-(config.repeat_threshold - 1) :])
        current_sm = record.soil_moisture
        # Chỉ đếm record có Soil_Moisture thật. Window [None, 55] không được
        # tính là hai giá trị có thể so sánh, tránh false positive khi có missing.
        comparable = [r for r in window if r.soil_moisture is not None]
        if (
            len(comparable) >= config.repeat_threshold - 1
            and all(r.soil_moisture == current_sm for r in comparable)
        ):
            return ValidationResult(
                is_valid=False,
                status="suspicious_repeat",
                reason=(
                    f"Soil_Moisture={current_sm} unchanged for "
                    f">={config.repeat_threshold} consecutive steps"
                ),
            )

    return ValidationResult(is_valid=True, status="valid")


def validate_live_record(
    record: RawRecord,
    config: ValidationConfig = DEFAULT_CONFIG,
) -> ValidationResult:
    """Validate một live sensor record với rule missing-value thoáng hơn.

    Khác với :func:`validate_record` yêu cầu **tất cả** field số phải có mặt,
    hàm này xem các kênh phụ như temperature, humidity, light, drip, mist, fan
    là optional.

    Rules
    -----
    * ``soil_moisture`` là **kênh chính**: nếu là ``None`` thì trả
      ``is_valid=False`` với ``status="missing"`` để bước preprocess tạo
      ``preprocess_status="skipped"``.
    * Các kênh phụ có thể thiếu; giá trị ``None`` được chấp nhận.
    * Field nào có mặt thì bắt buộc hữu hạn và nằm trong ngưỡng vật lý.

    Hàm này cố ý **không** detect suspicious-repeat vì live path thường không
    có đủ history phía trước tại thời điểm validate.

    Parameters
    ----------
    record:
        Live sensor record cần validate.
    config:
        Ngưỡng vật lý. Mặc định là :data:`DEFAULT_CONFIG`.

    Returns
    -------
    ValidationResult
        ``is_valid=True`` chỉ khi ``soil_moisture`` có mặt và mọi field có mặt
        đều hữu hạn, nằm trong ngưỡng.
    """
    # Guard cho kênh chính: không có measurement thì Kalman không update được.
    if record.soil_moisture is None:
        return ValidationResult(
            is_valid=False,
            status="missing",
            reason="soil_moisture is absent; Kalman measurement-update step skipped",
        )

    out_of_range = []
    for attr, min_attr, max_attr in _RANGE_CHECKS:
        val = getattr(record, attr)
        if val is None:
            continue  # kênh phụ vắng mặt được chấp nhận trong live path
        if not math.isfinite(val):
            out_of_range.append(f"{attr} is non-finite ({val!r})")
            continue
        lo: float = getattr(config, min_attr)
        hi: float = getattr(config, max_attr)
        if not (lo <= val <= hi):
            out_of_range.append(f"{attr}={val:.4g} not in [{lo}, {hi}]")

    if out_of_range:
        return ValidationResult(
            is_valid=False,
            status="out_of_range",
            reason="; ".join(out_of_range),
        )

    return ValidationResult(is_valid=True, status="valid")


def validate_batch(
    records: Sequence[RawRecord],
    config: ValidationConfig = DEFAULT_CONFIG,
) -> list[ValidationResult]:
    """Validate một sequence records với context rolling để phát hiện repeat.

    Mỗi record được validate với sliding window gồm **tất cả** record trước đó,
    không chỉ record valid. Logic repeat bên trong :func:`validate_record`
    đã tự lọc ``None`` Soil_Moisture khi đếm sample so sánh được.

    Parameters
    ----------
    records:
        Records cần validate theo thứ tự thời gian.
    config:
        Cấu hình validation.

    Returns
    -------
    list[ValidationResult]
        Một kết quả cho mỗi input record, cùng thứ tự.
    """
    results: list[ValidationResult] = []
    history: list[RawRecord] = []

    for record in records:
        result = validate_record(record, prev_records=history, config=config)
        results.append(result)
        # Mở rộng context window bằng tất cả record, dù valid hay không.
        history.append(record)
        if len(history) > config.repeat_threshold:
            history.pop(0)

    return results
