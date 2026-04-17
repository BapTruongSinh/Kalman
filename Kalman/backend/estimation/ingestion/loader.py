"""
Loader CSV cho dataset greenhouse.

Đọc CSV greenhouse, ví dụ ``ARX/greenhouse_data.csv``; nếu đứng trong
``Kalman/backend`` thì dùng ``../../ARX/greenhouse_data.csv``. Kết quả được
chuyển thành list dataclass :class:`RawRecord`, sau đó có helper
:func:`split_chronological` để chia train/validation/test theo tỉ lệ 60/20/20.

Ghi chú thiết kế
----------------
- ``RawRecord`` là frozen dataclass để code phía sau không sửa dữ liệu gốc.
- Các field số có kiểu ``float | None``; None nghĩa là giá trị bị thiếu hoặc
  không parse được từ file nguồn.
- Các cột ``Month``, ``Season``, ``Soil_Low_SP``, ``Soil_High_SP`` được đọc
  từ CSV nhưng không đưa vào typed field vì pipeline v1 chưa cần.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Format timestamp trong CSV.
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# Các cột số mà pipeline estimation thật sự dùng.
_NUMERIC_COLS = (
    "Soil_Moisture",
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
)


# Cấu trúc dữ liệu.

@dataclass(frozen=True)
class RawRecord:
    """Một row từ dataset greenhouse sau khi ép kiểu.

    ``row_index`` là vị trí 0-based trong file gốc để khi validation lỗi
    có thể truy ngược về dòng nguồn.
    """

    timestamp: datetime
    soil_moisture: float | None
    temperature: float | None
    humidity: float | None
    light: float | None
    drip: float | None
    fan: float | None
    mist: float | None
    row_index: int


@dataclass
class DatasetSplit:
    """Các slice train/validation/test được chia theo thứ tự thời gian."""

    train: list[RawRecord]
    validation: list[RawRecord]
    test: list[RawRecord]

    @property
    def total(self) -> int:
        return len(self.train) + len(self.validation) + len(self.test)


# Loader.

def load_csv(path: Path | str) -> list[RawRecord]:
    """Parse CSV greenhouse thành list :class:`RawRecord`.

    Row có timestamp không parse được sẽ bị bỏ qua và log warning.
    Field số không convert được sang float sẽ thành ``None`` để validator
    đánh dấu ở bước sau.

    Tham số
    -------
    path:
        Đường dẫn tuyệt đối hoặc tương đối tới file CSV.

    Trả về
    ------
    list[RawRecord]
        Records theo thứ tự trong file.

    Lỗi
    ---
    FileNotFoundError
        Nếu file không tồn tại.
    ValueError
        Nếu file không có row hoặc thiếu cột bắt buộc.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    records: list[RawRecord] = []
    skipped = 0

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")

        # Kiểm tra các cột bắt buộc có tồn tại không.
        header = set(reader.fieldnames)
        required = {"Timestamp"} | set(_NUMERIC_COLS)
        missing_cols = required - header
        if missing_cols:
            raise ValueError(
                f"CSV missing required columns: {sorted(missing_cols)}"
            )

        for line_no, row in enumerate(reader):
            raw_ts = row.get("Timestamp", "").strip()
            try:
                # Timestamp trong CSV không có timezone nên coi là UTC để
                # DateTimeField(use_tz=True) không warning khi lưu sample_ts.
                ts = datetime.strptime(raw_ts, _TS_FORMAT).replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(
                    "Row %d: unparseable timestamp %r — skipped",
                    line_no,
                    raw_ts,
                )
                skipped += 1
                continue

            records.append(
                RawRecord(
                    timestamp=ts,
                    soil_moisture=_to_float(row, "Soil_Moisture", line_no),
                    temperature=_to_float(row, "Temperature", line_no),
                    humidity=_to_float(row, "Humidity", line_no),
                    light=_to_float(row, "Light", line_no),
                    drip=_to_float(row, "Drip", line_no),
                    mist=_to_float(row, "Mist", line_no),
                    fan=_to_float(row, "Fan", line_no),
                    row_index=line_no,
                )
            )

    if not records:
        raise ValueError(f"No parseable rows found in {path}")

    if skipped:
        logger.warning("%d rows skipped due to bad timestamps", skipped)

    logger.info("Loaded %d records from %s", len(records), path)
    return records


def split_chronological(
    records: list[RawRecord],
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> DatasetSplit:
    """Chia records thành train / validation / test theo thứ tự thời gian.

    Records được sort phòng thủ theo timestamp trước khi chia để input lệch
    thứ tự, ví dụ query MySQL thiếu ORDER BY, không tạo split sai thứ tự.

    Tham số
    -------
    records:
        Records cần chia, phải không rỗng và đủ lớn để cả ba slice đều có dữ liệu.
    train_ratio:
        Tỉ lệ train, mặc định 0.60 theo ADR-003.
    val_ratio:
        Tỉ lệ validation, mặc định 0.20. Test = 1 - train - val.

    Lỗi
    ---
    ValueError
        Nếu tỉ lệ không hợp lệ, records rỗng, hoặc dataset quá nhỏ.
    """
    if not records:
        raise ValueError("Cannot split an empty record list")
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1):
        raise ValueError("train_ratio and val_ratio must each be in (0, 1)")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1.0")

    # Sort phòng thủ cho nguồn MySQL/query hoặc CSV bị đảo dòng.
    # Sort của Python stable nên record trùng timestamp giữ thứ tự gốc.
    records = sorted(records, key=lambda r: r.timestamp)

    n = len(records)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val

    if n_train < 1 or n_val < 1 or n_test < 1:
        raise ValueError(
            f"Dataset too small ({n} records) to produce non-empty train/val/test splits "
            f"with ratios {train_ratio}/{val_ratio}/{1 - train_ratio - val_ratio:.2f}. "
            f"Got n_train={n_train}, n_val={n_val}, n_test={n_test}."
        )

    train = records[:n_train]
    validation = records[n_train : n_train + n_val]
    test = records[n_train + n_val :]

    logger.info(
        "Split: train=%d  val=%d  test=%d  (total=%d)",
        len(train),
        len(validation),
        len(test),
        n,
    )
    return DatasetSplit(train=train, validation=validation, test=test)


# Helpers.

def _to_float(row: dict[str, str], col: str, line_no: int) -> float | None:
    """Convert một ô CSV sang float, lỗi thì trả None."""
    raw = row.get(col, "").strip()
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        logger.debug(
            "Row %d: column %r value %r is not numeric — treated as None",
            line_no,
            col,
            raw,
        )
        return None
