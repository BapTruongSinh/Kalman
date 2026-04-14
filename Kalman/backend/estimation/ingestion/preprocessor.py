"""
Preprocessing policies for greenhouse sensor data.

After validation, each record with an invalid reading must be handled by
one of three policies before it can enter the estimation pipeline:

keep_last
    Replace ALL fields of an invalid record with the last known good values.
    This applies to both missing (None) fields *and* out-of-range non-None
    values — both must not reach the ARX/Kalman pipeline unchanged.
    Produces ``preprocess_status="kept_last"`` (or ``"valid"`` for records
    that did not need substitution).

interpolate
    Linearly interpolate between the last valid value and the next valid
    value for every field of an invalid record.  Out-of-range non-None values
    are treated the same as missing values — the raw measurement is discarded.
    Falls back to keep_last when no next valid value is available.
    Produces ``preprocess_status="interpolated"``.

skip
    Set all effective field values to ``None`` for invalid records.
    ``preprocess_status="skipped"``.  The Kalman cycle must handle None
    measurement by skipping the measurement-update step.  This avoids
    passing out-of-range values downstream while keeping the record in the
    timeline for bookkeeping.

Regardless of policy, records whose ``ValidationResult.status`` is
``"valid"`` come through unchanged with ``preprocess_status="valid"``.

Note: ``preprocess_status`` string values match the choices defined in
``estimation.models.PipelineCycle.PreprocessStatus``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from .loader import RawRecord
from .validator import ValidationResult

logger = logging.getLogger(__name__)

# Numeric fields that can be preprocessed
_FIELDS = ("soil_moisture", "temperature", "humidity", "light", "drip", "mist", "fan")

# Policy string literals — must match ExperimentConfig.PreprocessPolicy choices
KEEP_LAST = "keep_last"
INTERPOLATE = "interpolate"
SKIP = "skip"

VALID_POLICIES = (KEEP_LAST, INTERPOLATE, SKIP)


# ─── Processed record ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProcessedRecord:
    """A record after preprocessing has been applied.

    ``raw`` and ``validation`` are kept for full traceability.
    The ``*`` numeric fields hold the effective values to be fed to the
    estimation pipeline; they may be ``None`` only when policy=``skip``
    and no substitution was possible.
    """

    raw: RawRecord
    validation: ValidationResult
    preprocess_status: str  # valid | kept_last | interpolated | skipped

    # Effective values after preprocessing
    soil_moisture: float | None
    temperature: float | None
    humidity: float | None
    light: float | None
    drip: float | None
    mist: float | None
    fan: float | None


# ─── Public API ───────────────────────────────────────────────────────────────

def apply_preprocessing(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
    policy: str = KEEP_LAST,
) -> list[ProcessedRecord]:
    """Apply preprocessing policy to a full sequence of records.

    Parameters
    ----------
    records:
        Raw records in chronological order.
    validations:
        One :class:`~validator.ValidationResult` per record (same order).
    policy:
        One of ``"keep_last"``, ``"interpolate"``, or ``"skip"``.

    Returns
    -------
    list[ProcessedRecord]
        One processed record per input record.

    Raises
    ------
    ValueError
        If ``records`` and ``validations`` have different lengths, or
        ``policy`` is not one of the allowed values.
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


# ─── Policy implementations ───────────────────────────────────────────────────

def _apply_keep_last(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
) -> list[ProcessedRecord]:
    """Keep-last-valid: substitute every field of an invalid record.

    When a record fails validation — whether due to a None field *or* an
    out-of-range value — ALL of its effective field values are replaced with
    the most recently seen valid measurement.  This ensures that out-of-range
    non-None values never reach the estimation pipeline.
    """
    last_valid: dict[str, float | None] = {f: None for f in _FIELDS}
    result: list[ProcessedRecord] = []

    for record, vr in zip(records, validations):
        if vr.is_valid:
            # Update last-known-good values and pass through unchanged
            for f in _FIELDS:
                val = getattr(record, f)
                if val is not None:
                    last_valid[f] = val
            result.append(_make_processed(record, vr, "valid", last_valid))
        else:
            # Invalid record: substitute ALL fields with last known good values.
            # Includes out_of_range non-None values — do not pass them downstream.
            effective = {f: last_valid[f] for f in _FIELDS}
            result.append(_make_processed(record, vr, "kept_last", effective))

    return result


def _apply_interpolate(
    records: Sequence[RawRecord],
    validations: Sequence[ValidationResult],
) -> list[ProcessedRecord]:
    """Linear interpolation between adjacent valid values.

    For each invalid record, ALL fields are interpolated between the last
    and next valid values.  Out-of-range non-None values are discarded —
    they are treated identically to missing (None) values for interpolation
    purposes.  Falls back to keep_last if no next-valid exists.
    """
    n = len(records)

    # Precompute per-field: index of next valid-and-non-None source value
    next_valid_idx: dict[str, list[int | None]] = {f: [None] * n for f in _FIELDS}
    for f in _FIELDS:
        nv: int | None = None
        for i in range(n - 1, -1, -1):
            if validations[i].is_valid and getattr(records[i], f) is not None:
                nv = i
            next_valid_idx[f][i] = nv

    last_valid_val: dict[str, float | None] = {f: None for f in _FIELDS}
    # Track the record index of the last valid value per field for gap calculation
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

        # Invalid record: interpolate ALL fields regardless of raw value.
        # Raw values are not trusted when vr.is_valid is False.
        effective: dict[str, float | None] = {}
        for f in _FIELDS:
            lv = last_valid_val[f]
            nv_idx = next_valid_idx[f][i]

            if lv is None and nv_idx is None:
                # No data on either side — keep None
                effective[f] = None
            elif lv is None:
                # No prior valid → borrow from the next valid record
                effective[f] = getattr(records[nv_idx], f)  # type: ignore[index]
            elif nv_idx is None:
                # No next valid → fall back to last valid
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
    """Pass valid records through; set all effective values to None for invalid ones.

    Skipped records expose ``None`` for every field so that the Kalman cycle
    can detect them and skip the measurement-update step.  Out-of-range
    non-None raw values are converted to ``None`` — they must not reach the
    estimation pipeline.
    """
    result: list[ProcessedRecord] = []
    for record, vr in zip(records, validations):
        if vr.is_valid:
            effective = {f: getattr(record, f) for f in _FIELDS}
            result.append(_make_processed(record, vr, "valid", effective))
        else:
            # Skipped: expose None for all fields regardless of raw values.
            effective = {f: None for f in _FIELDS}
            result.append(_make_processed(record, vr, "skipped", effective))
    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

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
    """Build a :class:`ProcessedRecord` for one record using skip policy.

    This is the correct policy for live sensor ingestion: if a reading is
    invalid there is no historical context to interpolate from, so all
    effective field values are set to ``None`` and the Kalman cycle skips
    the measurement-update step.

    Parameters
    ----------
    record:
        Raw sensor record (single sample from a device).
    validation:
        Result of calling :func:`~validator.validate_record` on *record*.

    Returns
    -------
    ProcessedRecord
        ``preprocess_status="valid"`` when the reading passes validation;
        ``preprocess_status="skipped"`` with all-``None`` effective values otherwise.
    """
    if validation.is_valid:
        effective: dict[str, float | None] = {f: getattr(record, f) for f in _FIELDS}
        return _make_processed(record, validation, "valid", effective)
    effective = {f: None for f in _FIELDS}
    return _make_processed(record, validation, "skipped", effective)
