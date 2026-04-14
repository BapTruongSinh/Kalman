"""
estimation.ingestion
====================
Offline dataset ingestion and preprocessing for the Adaptive Kalman pipeline.

Public API
----------
- :func:`load_csv` — parse greenhouse CSV into :class:`RawRecord` list
- :func:`split_chronological` — 60/20/20 chronological split
- :func:`validate_batch` — validate a record sequence (with repeat detection)
- :func:`validate_record` — validate a single record
- :func:`apply_preprocessing` — apply keep_last / interpolate / skip policy
- :func:`preprocess_single` — skip-policy preprocessing for one live sample
- :class:`RawRecord` — typed raw data record
- :class:`DatasetSplit` — train/val/test container
- :class:`ValidationResult` — per-record validation outcome
- :class:`ValidationConfig` — configurable physical bounds
- :class:`ProcessedRecord` — record after preprocessing
- :data:`KEEP_LAST` / :data:`INTERPOLATE` / :data:`SKIP` — policy name constants
- :data:`VALID_POLICIES` — tuple of all accepted policy strings
"""

from .loader import DatasetSplit, RawRecord, load_csv, split_chronological
from .preprocessor import (
    INTERPOLATE,
    KEEP_LAST,
    SKIP,
    VALID_POLICIES,
    ProcessedRecord,
    apply_preprocessing,
    preprocess_single,
)
from .validator import ValidationConfig, ValidationResult, validate_batch, validate_record

__all__ = [
    # loader
    "load_csv",
    "split_chronological",
    "RawRecord",
    "DatasetSplit",
    # validator
    "validate_record",
    "validate_batch",
    "ValidationResult",
    "ValidationConfig",
    # preprocessor
    "apply_preprocessing",
    "preprocess_single",
    "ProcessedRecord",
    "KEEP_LAST",
    "INTERPOLATE",
    "SKIP",
    "VALID_POLICIES",
]
