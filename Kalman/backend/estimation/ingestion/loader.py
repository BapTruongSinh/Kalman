"""
CSV loader for greenhouse dataset.

Reads a greenhouse CSV (e.g. repo ``ARX/greenhouse_data.csv``; from
``Kalman/backend`` use ``../../ARX/greenhouse_data.csv``) into a list of
:class:`RawRecord` dataclasses, then provides a :func:`split_chronological`
helper for 60/20/20 train/validation/test slices.

Design notes
------------
- ``RawRecord`` is frozen so downstream code cannot mutate source data.
- Numeric fields are ``float | None``; None means the value was absent or
  non-parseable in the source file (logged by the caller).
- Columns ``Month``, ``Season``, ``Soil_Low_SP``, ``Soil_High_SP`` are read
  but not exposed as typed fields — they are not needed by the v1 estimation
  pipeline and are intentionally ignored to keep the record slim.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Timestamp format in the CSV ─────────────────────────────────────────────
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# ─── Numeric columns that the estimation pipeline actually uses ───────────────
_NUMERIC_COLS = (
    "Soil_Moisture",
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
)


# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RawRecord:
    """One row from the greenhouse dataset after type-coercion.

    ``row_index`` is the 0-based position in the original file so callers
    can correlate validation errors back to a source line number.
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
    """Chronological train/validation/test slices of a dataset."""

    train: list[RawRecord]
    validation: list[RawRecord]
    test: list[RawRecord]

    @property
    def total(self) -> int:
        return len(self.train) + len(self.validation) + len(self.test)


# ─── Loader ───────────────────────────────────────────────────────────────────

def load_csv(path: Path | str) -> list[RawRecord]:
    """Parse a greenhouse CSV into a list of :class:`RawRecord`.

    Rows with unparseable timestamps are skipped and logged as warnings.
    Numeric fields that cannot be converted to float are set to ``None``
    (the validator will flag them later).

    Parameters
    ----------
    path:
        Absolute or relative path to the CSV file.

    Returns
    -------
    list[RawRecord]
        Records in file order (oldest first).

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file has no rows or is missing required columns.
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

        # Validate required columns are present
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
                # Naive CSV times are treated as UTC so ORM DateTimeField(use_tz=True)
                # does not emit a warning per row when persisting PipelineCycle.sample_ts.
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
    """Split records into chronological train / validation / test slices.

    Records are sorted defensively by timestamp before splitting so that
    out-of-order inputs (e.g. from a MySQL query without ORDER BY, or a
    manually reordered CSV) do not silently produce a non-chronological split.

    Parameters
    ----------
    records:
        Records to split (must be non-empty and large enough for all three
        slices to be non-empty).
    train_ratio:
        Fraction for training. Default 0.60 (ADR-003).
    val_ratio:
        Fraction for validation. Default 0.20. Test = 1 - train - val.

    Raises
    ------
    ValueError
        If ratios are invalid, the records list is empty, or the dataset is
        too small to produce non-empty train / validation / test slices.
    """
    if not records:
        raise ValueError("Cannot split an empty record list")
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1):
        raise ValueError("train_ratio and val_ratio must each be in (0, 1)")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1.0")

    # Sort defensively — handles MySQL/query sources and reordered CSV files.
    # Python's sort is stable, so equal-timestamp records keep their original order.
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _to_float(row: dict[str, str], col: str, line_no: int) -> float | None:
    """Convert a CSV cell to float, returning None on failure."""
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
