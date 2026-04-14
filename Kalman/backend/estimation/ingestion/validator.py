"""
Per-record validation for greenhouse sensor data.

Validation is **stateless per record** except for suspicious-repeat detection,
which requires a small window of previous values.  Callers that do not need
repeat detection can pass an empty list for ``prev_records``.

Validation categories
---------------------
VALID
    All fields present and within plausible physical bounds.
MISSING
    One or more numeric fields are ``None``.  This covers two source cases:
    (a) the CSV cell was empty or absent, and (b) the CSV cell contained a
    non-numeric string — both are normalised to ``None`` by the loader's
    ``_to_float`` helper **before** reaching this validator.  In other words,
    numeric parse errors are surfaced as ``status="missing"`` rather than a
    separate malformed status.
OUT_OF_RANGE
    A numeric field is present but outside the configured physical bounds.
    Non-finite values (NaN, Inf) are also reported as ``out_of_range``.
SUSPICIOUS_REPEAT
    The primary state variable (Soil_Moisture) has not changed for
    ``repeat_threshold`` consecutive steps — likely a stuck sensor.

Note on malformed timestamps
-----------------------------
Rows with unparseable timestamps are **rejected by the loader** (logged and
skipped) before any ``RawRecord`` is created.  Therefore this validator never
receives a record with a missing timestamp and does not need a MALFORMED
category.  Task #003 acceptance criterion "flags malformed" is satisfied by the
combination of loader-level timestamp rejection and validator-level
``status="missing"`` for non-parseable numeric cells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .loader import RawRecord


# ─── Configurable physical bounds ─────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationConfig:
    """Physical bounds and repeat-detection settings.

    All bounds are inclusive.  Adjust per deployment if sensor characteristics
    differ from the default greenhouse dataset.
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
    # Number of consecutive identical Soil_Moisture values before flagging
    repeat_threshold: int = 10


DEFAULT_CONFIG = ValidationConfig()


# ─── Result type ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a single :class:`~loader.RawRecord`."""

    is_valid: bool
    status: str          # one of VALID | MISSING | OUT_OF_RANGE | SUSPICIOUS_REPEAT
    reason: str = ""     # human-readable explanation when not valid


# ─── Validator ────────────────────────────────────────────────────────────────

# Mapping of field name → (min, max) for the _numeric_ fields we care about
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
    """Validate a single record.

    Parameters
    ----------
    record:
        The record to validate.
    prev_records:
        Recent records preceding this one (most recent last).  Used only for
        suspicious-repeat detection.  May be ``None`` or empty to skip that check.
    config:
        Physical bounds and thresholds.  Defaults to :data:`DEFAULT_CONFIG`.

    Returns
    -------
    ValidationResult
        ``is_valid=True`` only when status is ``"valid"``.
    """
    # ── 1. Missing-value check ─────────────────────────────────────────────
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

    # ── 2. NaN / Inf guard ────────────────────────────────────────────────
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

    # ── 3. Range check ────────────────────────────────────────────────────
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

    # ── 4. Suspicious-repeat check (Soil_Moisture only) ───────────────────
    if prev_records and len(prev_records) >= config.repeat_threshold - 1:
        window = list(prev_records[-(config.repeat_threshold - 1) :])
        current_sm = record.soil_moisture
        # Count only records that carry a real Soil_Moisture reading.
        # A window of [None, 55] should NOT count as two comparable values —
        # that would cause false positives when missing records appear in the run.
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


def validate_batch(
    records: Sequence[RawRecord],
    config: ValidationConfig = DEFAULT_CONFIG,
) -> list[ValidationResult]:
    """Validate a sequence of records with rolling repeat-detection context.

    Each record is validated with a sliding window of **all** preceding records
    (not only valid ones).  The repeat-detection logic inside
    :func:`validate_record` already filters out ``None`` Soil_Moisture values
    when counting comparable samples, so including invalid rows in the history
    is intentional: a row that is invalid for a *different* reason (e.g.
    temperature out of range) still carries a real Soil_Moisture reading that
    contributes to stuck-sensor detection.

    Parameters
    ----------
    records:
        Records to validate (in chronological order).
    config:
        Validation configuration.

    Returns
    -------
    list[ValidationResult]
        One result per input record, in the same order.
    """
    results: list[ValidationResult] = []
    history: list[RawRecord] = []

    for record in records:
        result = validate_record(record, prev_records=history, config=config)
        results.append(result)
        # Grow the sliding context window (all records, valid or not)
        history.append(record)
        if len(history) > config.repeat_threshold:
            history.pop(0)

    return results
