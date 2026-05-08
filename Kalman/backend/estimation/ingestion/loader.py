"""Typed raw sensor sample used by live ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawRecord:
    """One raw live sensor sample after API payload coercion.

    ``row_index`` is retained as a generic trace index for validation messages
    and tests. Live API samples set it to the current cycle index candidate.
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
