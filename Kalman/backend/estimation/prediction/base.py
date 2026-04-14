"""
Prediction adapter contract for the Adaptive Kalman estimation pipeline.

Any model that produces next-step ``Soil_Moisture`` predictions must implement
``PredictionAdapter``.  The ARX baseline lives in ``arx_adapter.py``; future
LightGBM / XGBoost adapters follow the same boundary so the Kalman estimator
(task #005) never depends on model internals.

Design constraints
------------------
- ``predict()`` must never raise: use ``status="error"`` or ``"unavailable"``
  so the Kalman cycle can proceed with prediction unavailable rather than
  crashing.
- All numeric field values in ``PredictionInput.history`` are expected to be
  non-``None`` (the preprocessor, task #003, fills them in beforehand).
- ``model_kind`` is a short lowercase identifier (``"arx"``, ``"lightgbm"``, …)
  stored alongside each cycle log row for audit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from ..ingestion import ProcessedRecord


@dataclass
class PredictionInput:
    """Window of recent preprocessed records needed for a 1-step prediction.

    Records must be in chronological order (oldest first).
    All effective field values should be non-``None``; the preprocessor must
    have handled substitution before calling ``predict()``.

    Attributes
    ----------
    history:
        At least ``adapter.min_history_len`` records.
    """

    history: list[ProcessedRecord] = field(default_factory=list)


@dataclass(frozen=True)
class PredictionResult:
    """Outcome of a single 1-step prediction.

    Attributes
    ----------
    value:
        Predicted next ``Soil_Moisture``; ``None`` when unavailable.
    status:
        ``"ok"``         — prediction produced successfully.
        ``"unavailable"`` — model not trained or not enough history.
        ``"error"``      — computation failed; ``reason`` has details.
    model_kind:
        Short identifier matching ``PredictionAdapter.model_kind``.
    reason:
        Human-readable explanation when ``status != "ok"``.
    """

    value: float | None
    status: str
    model_kind: str
    reason: str = ""


class PredictionAdapter(ABC):
    """Abstract base for all prediction models in the estimation pipeline.

    Implement this class to wrap a specific model behind the boundary that
    the Kalman estimator calls.  The contract keeps model internals hidden so
    adapters are swappable without touching the estimator.

    Required properties and methods
    --------------------------------
    model_kind        — short lowercase identifier, e.g. ``"arx"``
    is_trained        — ``True`` when a fitted model is ready for prediction
    min_history_len   — minimum preceding records required by ``predict()``
    train()           — offline fit on a sequence of ``ProcessedRecord``
    predict()         — 1-step prediction; must not raise
    save_artifact()   — persist the fitted model to a file
    load_artifact()   — classmethod; restore a previously saved adapter
    """

    @property
    @abstractmethod
    def model_kind(self) -> str:
        """Short lowercase identifier for the model family, e.g. ``"arx"``."""

    @property
    @abstractmethod
    def is_trained(self) -> bool:
        """``True`` when the adapter holds a fitted model ready for prediction."""

    @property
    @abstractmethod
    def min_history_len(self) -> int:
        """Minimum number of preceding records required to call ``predict()``."""

    @abstractmethod
    def train(
        self,
        records: Sequence[ProcessedRecord],
        *,
        val_records: Sequence[ProcessedRecord] | None = None,
    ) -> dict[str, object]:
        """Fit the model on *records* and return a metrics summary.

        Parameters
        ----------
        records:
            Training records in chronological order.  Must have enough rows
            for the configured lag order.
        val_records:
            Optional held-out records for reporting validation metrics.

        Returns
        -------
        dict
            Model-agnostic summary with at least these keys:
            ``model_kind``, ``n_train``, ``train_metrics``.
        """

    @abstractmethod
    def predict(self, inp: PredictionInput) -> PredictionResult:
        """Return a 1-step prediction from recent history.

        Must **never raise**.  Returns ``status="error"`` or
        ``status="unavailable"`` on any failure so the Kalman cycle can
        continue without the prediction step.

        Parameters
        ----------
        inp:
            Recent history; must have at least ``min_history_len`` records.

        Returns
        -------
        PredictionResult
            Always a valid object; inspect ``status`` before using ``value``.
        """

    @abstractmethod
    def save_artifact(self, path: Path) -> None:
        """Persist the trained model to *path*.

        Raises
        ------
        RuntimeError
            If the model has not been trained yet.
        """

    @classmethod
    @abstractmethod
    def load_artifact(cls, path: Path) -> "PredictionAdapter":
        """Restore a previously saved adapter from *path*.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        ValueError
            If the artifact format is unrecognised.
        """
