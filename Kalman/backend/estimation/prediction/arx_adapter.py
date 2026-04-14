"""
ARX prediction adapter — wraps ``arx_pipeline.py`` behind ``PredictionAdapter``.

This module exposes ``ARXPredictionAdapter``, the v1 baseline prediction model.
It reproduces the OLS training and 1-step prediction logic from ``arx_pipeline.py``
using only NumPy and ``ProcessedRecord`` objects so no notebook-level code is
imported at runtime.

Two artifact formats are supported by ``load_artifact()``:

- **Native format** (written by ``save_artifact()``): contains an
  ``"adapter_version"`` key.
- **Pipeline format** (written by ``arx_pipeline.save_artifact()``): contains
  ``model="ARX"`` and the ``model_config`` / ``theta_hat`` structure produced
  by the existing notebook pipeline.  ``best_candidate`` is preferred when
  present.

Training example::

    from estimation.ingestion import ProcessedRecord
    from estimation.prediction import ARXPredictionAdapter, ARXTrainConfig

    adapter = ARXPredictionAdapter(ARXTrainConfig(na=2, nb=2, nk=1))
    summary = adapter.train(train_records, val_records=val_records)
    adapter.save_artifact(Path("run_001_arx.json"))

Prediction example::

    from estimation.prediction import ARXPredictionAdapter, PredictionInput

    adapter = ARXPredictionAdapter.load_artifact(Path("arx_model.json"))
    result  = adapter.predict(PredictionInput(history=recent_records))
    if result.status == "ok":
        y_hat = result.value
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ..ingestion import ProcessedRecord
from .base import PredictionAdapter, PredictionInput, PredictionResult

logger = logging.getLogger(__name__)

# ── Field mapping ─────────────────────────────────────────────────────────────
# ProcessedRecord attribute name → DataFrame / ARX column name
_FIELD_MAP: dict[str, str] = {
    "soil_moisture": "Soil_Moisture",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "light": "Light",
    "drip": "Drip",
    "mist": "Mist",
    "fan": "Fan",
}

# ARX column name → ProcessedRecord attribute name (reverse of _FIELD_MAP)
_COL_TO_ATTR: dict[str, str] = {v: k for k, v in _FIELD_MAP.items()}

_DEFAULT_INPUT_COLS: tuple[str, ...] = (
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
)


# ── Configuration ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ARXTrainConfig:
    """Hyperparameters for offline ARX model training.

    Attributes
    ----------
    na:
        AR order — number of lagged output terms.
    nb:
        Exogenous input order — number of lagged input terms per channel.
    nk:
        Input delay (dead-time).  ``nk=1`` means no dead-time beyond one step.
    include_intercept:
        Whether to add a constant term to the regression.
    input_cols:
        Ordered tuple of ARX/DataFrame column names (e.g. ``"Temperature"``,
        ``"Humidity"``).  Must be drawn from ``_FIELD_MAP`` *values*.
    output_col:
        Output column name (e.g. ``"Soil_Moisture"``).  Must be one of the
        ``_FIELD_MAP`` *values*.
    """

    na: int = 2
    nb: int = 2
    nk: int = 1
    include_intercept: bool = False
    input_cols: tuple[str, ...] = _DEFAULT_INPUT_COLS
    output_col: str = "Soil_Moisture"

    def __post_init__(self) -> None:
        """Validate hyperparameters at construction time."""
        _known: frozenset[str] = frozenset(_FIELD_MAP.values())
        if self.na < 1:
            raise ValueError(f"na must be >= 1, got {self.na!r}")
        if self.nb < 1:
            raise ValueError(f"nb must be >= 1, got {self.nb!r}")
        if self.nk < 1:
            raise ValueError(f"nk must be >= 1, got {self.nk!r}")
        if not self.input_cols:
            raise ValueError("input_cols must not be empty")
        bad = [c for c in self.input_cols if c not in _known]
        if bad:
            raise ValueError(
                f"Unknown input column(s): {bad}. "
                f"Supported: {sorted(_known)}"
            )
        if self.output_col not in _known:
            raise ValueError(
                f"Unknown output_col {self.output_col!r}. "
                f"Supported: {sorted(_known)}"
            )

    @property
    def max_lag(self) -> int:
        """Maximum lag index required for building the regression row."""
        return max(self.na, self.nb + self.nk - 1)

    @property
    def min_history_len(self) -> int:
        """Minimum history window size for a valid 1-step prediction."""
        return self.max_lag

    def param_names(self) -> list[str]:
        """Return ordered parameter names matching ``theta_hat``."""
        names = [f"a{lag}" for lag in range(1, self.na + 1)]
        for col in self.input_cols:
            for lag in range(1, self.nb + 1):
                names.append(f"b_{col}_{lag}")
        if self.include_intercept:
            names.append("intercept")
        return names

    def n_params(self) -> int:
        return len(self.param_names())


# ── Internal numerical helpers ────────────────────────────────────────────────


def _records_to_arrays(
    records: Sequence[ProcessedRecord],
    config: ARXTrainConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert a ``ProcessedRecord`` sequence to an OLS regression matrix.

    Mirrors ``arx_pipeline.build_regression_matrix`` but works directly on
    ``ProcessedRecord`` objects — no pandas dependency required.

    Returns
    -------
    x_mat : np.ndarray, shape ``(n_eff, n_params)``
    y_vec : np.ndarray, shape ``(n_eff,)``

    Raises
    ------
    ValueError
        If there are not enough records for the configured lag order.
    """
    n = len(records)
    max_lag = config.max_lag
    n_eff = n - max_lag
    if n_eff <= 0:
        raise ValueError(
            f"Not enough records ({n}) for max_lag={max_lag}; "
            f"need at least {max_lag + 1}"
        )

    out_attr = _COL_TO_ATTR.get(config.output_col, "soil_moisture")
    y = np.array(
        [float(getattr(records[i], out_attr)) for i in range(n)], dtype=float
    )

    input_arrays: list[np.ndarray] = []
    for col in config.input_cols:
        attr = _COL_TO_ATTR.get(col, col.lower())
        input_arrays.append(
            np.array(
                [float(getattr(records[i], attr)) for i in range(n)], dtype=float
            )
        )

    n_params = config.n_params()
    x_mat = np.zeros((n_eff, n_params), dtype=float)
    y_vec = np.zeros(n_eff, dtype=float)

    for row_idx in range(n_eff):
        t = row_idx + max_lag
        row: list[float] = []
        # AR part: lagged output
        for lag in range(1, config.na + 1):
            row.append(float(y[t - lag]))
        # Exogenous part: lagged inputs with dead-time nk
        for u in input_arrays:
            for lag in range(config.nk, config.nk + config.nb):
                row.append(float(u[t - lag]))
        if config.include_intercept:
            row.append(1.0)
        x_mat[row_idx] = row
        y_vec[row_idx] = float(y[t])

    return x_mat, y_vec


def _build_prediction_row(
    history: Sequence[ProcessedRecord],
    config: ARXTrainConfig,
) -> np.ndarray:
    """Build the regression row vector for a single 1-step prediction.

    Uses the most-recent ``config.min_history_len`` records in *history*
    via negative indexing so any extra earlier records are ignored.

    Parameters
    ----------
    history:
        At least ``config.min_history_len`` records, chronological order.
    config:
        Must match the config used during training.

    Returns
    -------
    np.ndarray, shape ``(n_params,)``
    """
    n = len(history)
    out_attr = _COL_TO_ATTR.get(config.output_col, "soil_moisture")
    y = np.array(
        [float(getattr(history[i], out_attr)) for i in range(n)], dtype=float
    )

    input_arrays: list[np.ndarray] = []
    for col in config.input_cols:
        attr = _COL_TO_ATTR.get(col, col.lower())
        input_arrays.append(
            np.array(
                [float(getattr(history[i], attr)) for i in range(n)], dtype=float
            )
        )

    row: list[float] = []
    # AR part: last na output values (lag 1 = most recent)
    for lag in range(1, config.na + 1):
        row.append(float(y[-lag]))
    # Exogenous part: last inputs with dead-time nk
    for u in input_arrays:
        for lag in range(config.nk, config.nk + config.nb):
            row.append(float(u[-lag]))
    if config.include_intercept:
        row.append(1.0)

    return np.array(row, dtype=float)


def _ols_fit(
    x_mat: np.ndarray, y_vec: np.ndarray
) -> tuple[np.ndarray, float]:
    """Ordinary least-squares fit.

    Returns
    -------
    theta : np.ndarray, shape ``(n_params,)``
    sigma2 : float — residual variance estimate
    """
    theta, _, _, _ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    n_obs, n_params = x_mat.shape
    resid = y_vec - x_mat @ theta
    sigma2 = float(np.dot(resid, resid) / max(1, n_obs - n_params))
    return theta, sigma2


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute RMSE, MAE, and R² between *y_true* and *y_pred*."""
    resid = y_true - y_pred
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    mae = float(np.mean(np.abs(resid)))
    ss_res = float(np.dot(resid, resid))
    ss_tot = float(np.dot(y_true - y_true.mean(), y_true - y_true.mean()))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0.0 else float("nan")
    return {"rmse": rmse, "mae": mae, "r2": r2}


# ── Adapter ───────────────────────────────────────────────────────────────────


class ARXPredictionAdapter(PredictionAdapter):
    """ARX baseline prediction adapter.

    Wraps offline OLS training and 1-step prediction behind the
    ``PredictionAdapter`` contract.  No notebook-level code is imported.

    Lifecycle
    ---------
    1. **Train**: ``adapter.train(train_records, val_records=val_records)``
    2. **Persist**: ``adapter.save_artifact(path)``
    3. **Reload**: ``ARXPredictionAdapter.load_artifact(path)``
    4. **Predict**: ``adapter.predict(PredictionInput(history=recent))``

    Loading ``arx_model.json``
    --------------------------
    ``load_artifact()`` accepts both the native format written by
    ``save_artifact()`` *and* the format written by the existing
    ``arx_pipeline.save_artifact()`` (from ``../ARX/arx_pipeline.py``).
    When ``"best_candidate"`` is present in the pipeline artifact, its
    ``model_config`` and ``theta_hat`` are used in preference to the
    baseline order.
    """

    _KIND = "arx"

    def __init__(self, train_config: ARXTrainConfig | None = None) -> None:
        self._config: ARXTrainConfig = train_config or ARXTrainConfig()
        self._theta: np.ndarray | None = None
        self._sigma2: float | None = None
        self._train_metrics: dict[str, float] | None = None
        self._val_metrics: dict[str, float] | None = None

    # ── PredictionAdapter interface ────────────────────────────────────────

    @property
    def model_kind(self) -> str:
        return self._KIND

    @property
    def is_trained(self) -> bool:
        return self._theta is not None

    @property
    def min_history_len(self) -> int:
        return self._config.min_history_len

    @property
    def train_config(self) -> ARXTrainConfig:
        """Return the ARX hyperparameter configuration."""
        return self._config

    @property
    def train_metrics(self) -> dict[str, float] | None:
        """Training-set metrics set after ``train()``, else ``None``."""
        return dict(self._train_metrics) if self._train_metrics else None

    @property
    def val_metrics(self) -> dict[str, float] | None:
        """Validation-set metrics set after ``train(val_records=…)``, else ``None``."""
        return dict(self._val_metrics) if self._val_metrics else None

    # ── Training ──────────────────────────────────────────────────────────

    def train(
        self,
        records: Sequence[ProcessedRecord],
        *,
        val_records: Sequence[ProcessedRecord] | None = None,
    ) -> dict[str, object]:
        """Offline OLS training on *records*.

        Parameters
        ----------
        records:
            Training records in chronological order.
        val_records:
            Optional held-out records for validation metric reporting.

        Returns
        -------
        dict
            Summary with keys: ``model_kind``, ``na``, ``nb``, ``nk``,
            ``n_params``, ``n_train``, ``sigma2``, ``train_metrics``, and
            optionally ``n_val`` / ``val_metrics``.

        Raises
        ------
        ValueError
            If *records* is too short for the configured lag order.
        """
        logger.info(
            "ARX training: %d records, na=%d nb=%d nk=%d",
            len(records),
            self._config.na,
            self._config.nb,
            self._config.nk,
        )

        x_mat, y_vec = _records_to_arrays(records, self._config)
        self._theta, self._sigma2 = _ols_fit(x_mat, y_vec)
        y_pred_train = x_mat @ self._theta
        self._train_metrics = _metrics(y_vec, y_pred_train)

        summary: dict[str, object] = {
            "model_kind": self._KIND,
            "na": self._config.na,
            "nb": self._config.nb,
            "nk": self._config.nk,
            "n_params": self._config.n_params(),
            "n_train": len(records),
            "sigma2": self._sigma2,
            "train_metrics": dict(self._train_metrics),
        }

        if val_records is not None and len(val_records) > self._config.min_history_len:
            try:
                x_val, y_val = _records_to_arrays(val_records, self._config)
                y_pred_val = x_val @ self._theta
                self._val_metrics = _metrics(y_val, y_pred_val)
                summary["n_val"] = len(val_records)
                summary["val_metrics"] = dict(self._val_metrics)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ARX: val metrics skipped: %s", exc)

        logger.info(
            "ARX training complete: sigma2=%.4f train_rmse=%.4f",
            self._sigma2,
            self._train_metrics["rmse"],
        )
        return summary

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, inp: PredictionInput) -> PredictionResult:
        """1-step ``Soil_Moisture`` prediction from recent history.

        Returns ``status="unavailable"`` (not an exception) when the model
        is not trained or the history window is too short.  Returns
        ``status="error"`` if the numeric computation fails.

        This method **never raises** — every failure path returns a
        ``PredictionResult`` with an appropriate ``status`` and ``reason``.

        Parameters
        ----------
        inp:
            Must have at least ``min_history_len`` records.  Fields must be
            non-``None`` (fill via preprocessor before calling predict).
            Passing ``None`` or a malformed object returns ``status="error"``.

        Returns
        -------
        PredictionResult
            Inspect ``status`` before using ``value``.
        """
        # ── Input safety guard ─────────────────────────────────────────────────
        # Extract history and its length before any logic so that None inp,
        # None history, or any non-sequence history object never propagates
        # as an unhandled exception.
        try:
            raw_history = inp.history  # type: ignore[union-attr]
            history: list = [] if raw_history is None else raw_history
            history_len: int = len(history)
        except Exception as exc:  # noqa: BLE001
            return PredictionResult(
                value=None,
                status="error",
                model_kind=self._KIND,
                reason=f"Invalid PredictionInput: {exc}",
            )
        # ──────────────────────────────────────────────────────────────────────

        if not self.is_trained:
            return PredictionResult(
                value=None,
                status="unavailable",
                model_kind=self._KIND,
                reason="Model not trained; call train() or load_artifact() first",
            )

        if history_len < self.min_history_len:
            return PredictionResult(
                value=None,
                status="unavailable",
                model_kind=self._KIND,
                reason=(
                    f"History too short: {history_len} < "
                    f"{self.min_history_len} records required for ARX prediction"
                ),
            )

        try:
            # Determine which ProcessedRecord attributes are required
            out_attr = _COL_TO_ATTR.get(self._config.output_col, "soil_moisture")
            input_attrs = [
                _COL_TO_ATTR.get(col, col.lower())
                for col in self._config.input_cols
            ]
            required_attrs = [out_attr] + input_attrs

            # Check for None values in required fields of recent records
            needed = history[-self.min_history_len:]
            none_fields: list[str] = []
            for rec in needed:
                for attr in required_attrs:
                    if getattr(rec, attr, None) is None:
                        none_fields.append(attr)

            if none_fields:
                return PredictionResult(
                    value=None,
                    status="unavailable",
                    model_kind=self._KIND,
                    reason=(
                        f"None values in required history fields: "
                        f"{sorted(set(none_fields))}"
                    ),
                )

            row = _build_prediction_row(history, self._config)
            assert self._theta is not None  # guarded by is_trained above
            y_hat = float(np.dot(row, self._theta))

            if not np.isfinite(y_hat):
                return PredictionResult(
                    value=None,
                    status="error",
                    model_kind=self._KIND,
                    reason=f"Non-finite prediction: {y_hat}",
                )

            return PredictionResult(
                value=y_hat,
                status="ok",
                model_kind=self._KIND,
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("ARX predict failed")
            return PredictionResult(
                value=None,
                status="error",
                model_kind=self._KIND,
                reason=f"Prediction error: {exc}",
            )

    # ── Artifact persistence ──────────────────────────────────────────────

    def save_artifact(self, path: Path) -> None:
        """Persist the trained model as a JSON artifact.

        The written file uses the *native* format understood by
        ``load_artifact()``.  It also contains enough information for a
        human to reconstruct the model manually.

        Raises
        ------
        RuntimeError
            If the model has not been trained yet.
        """
        if not self.is_trained:
            raise RuntimeError(
                "Cannot save: ARXPredictionAdapter has not been trained"
            )
        assert self._theta is not None

        payload: dict[str, Any] = {
            "model": "ARX",
            "adapter_version": "1",
            "model_config": {
                "na": self._config.na,
                "nb": self._config.nb,
                "nk": self._config.nk,
                "include_intercept": self._config.include_intercept,
                "input_cols": list(self._config.input_cols),
                "output_col": self._config.output_col,
            },
            "param_names": self._config.param_names(),
            "theta_hat": self._theta.tolist(),
            "sigma2": self._sigma2,
            "train_metrics": self._train_metrics,
            "val_metrics": self._val_metrics,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        logger.info("ARX artifact saved to %s", path)

    @classmethod
    def load_artifact(cls, path: Path) -> "ARXPredictionAdapter":
        """Restore a trained adapter from a JSON artifact.

        Supports two formats:

        - **Native** (``"adapter_version"`` key present): written by
          ``save_artifact()``.
        - **Pipeline** (``model="ARX"`` + ``"model_config"``): written by
          the existing ``arx_pipeline.save_artifact()``; ``"best_candidate"``
          config and theta are used when present.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        ValueError
            If the artifact format cannot be recognised.
        """
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")

        with path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        if "adapter_version" in data:
            return cls._load_native(data)
        if data.get("model") == "ARX" and "model_config" in data:
            return cls._load_pipeline_format(data)
        raise ValueError(
            f"Unrecognised artifact format in {path}: expected "
            "'adapter_version' key (native format) or model='ARX' with "
            "'model_config' (pipeline format)"
        )

    # ── Private loaders ───────────────────────────────────────────────────

    @classmethod
    def _load_native(cls, data: dict[str, Any]) -> "ARXPredictionAdapter":
        """Load native adapter-format artifact."""
        cfg_d = data["model_config"]
        config = ARXTrainConfig(
            na=int(cfg_d["na"]),
            nb=int(cfg_d["nb"]),
            nk=int(cfg_d["nk"]),
            include_intercept=bool(cfg_d.get("include_intercept", False)),
            input_cols=tuple(cfg_d.get("input_cols", _DEFAULT_INPUT_COLS)),
            output_col=str(cfg_d.get("output_col", "Soil_Moisture")),
        )
        theta = np.array(data["theta_hat"], dtype=float)
        if len(theta) != config.n_params():
            raise ValueError(
                f"Artifact theta has {len(theta)} parameters but config "
                f"expects {config.n_params()} "
                f"(na={config.na}, nb={config.nb}, nk={config.nk}, "
                f"{len(config.input_cols)} input channel(s))"
            )
        adapter = cls(train_config=config)
        adapter._theta = theta
        adapter._sigma2 = float(data["sigma2"]) if data.get("sigma2") is not None else None
        adapter._train_metrics = data.get("train_metrics")
        adapter._val_metrics = data.get("val_metrics")
        return adapter

    @classmethod
    def _load_pipeline_format(cls, data: dict[str, Any]) -> "ARXPredictionAdapter":
        """Load from ``arx_pipeline.save_artifact()`` format.

        Uses ``best_candidate`` config, theta, **and sigma2** when present;
        falls back to the top-level ``model_config`` / ``theta_hat`` /
        ``sigma2`` otherwise.
        """
        top_cfg_d: dict[str, Any] = data["model_config"]
        best_used = "best_candidate" in data and "theta_hat" in data["best_candidate"]

        if best_used:
            best: dict[str, Any] = data["best_candidate"]
            cfg_d: dict[str, Any] = best.get("model_config", top_cfg_d)
            theta_list: list[float] = best["theta_hat"]
            # Use best_candidate's sigma2 — consistent with the chosen theta
            sigma2_raw = best.get("sigma2")
            # Extract val metrics from best_candidate.val
            val_m_raw: dict[str, Any] = (
                best.get("val", {}).get("metrics_1step", {})
            )
        else:
            cfg_d = top_cfg_d
            theta_list = data["theta_hat"]
            sigma2_raw = data.get("sigma2")
            val_m_raw = (
                data.get("slices", {}).get("val", {}).get("metrics_1step", {})
            )

        config = ARXTrainConfig(
            na=int(cfg_d["na"]),
            nb=int(cfg_d["nb"]),
            nk=int(cfg_d["nk"]),
            include_intercept=bool(cfg_d.get("include_intercept", False)),
            input_cols=tuple(cfg_d.get("input_cols", _DEFAULT_INPUT_COLS)),
            output_col=str(cfg_d.get("output_col", "Soil_Moisture")),
        )
        theta = np.array(theta_list, dtype=float)
        if len(theta) != config.n_params():
            raise ValueError(
                f"Artifact theta has {len(theta)} parameters but config "
                f"expects {config.n_params()} "
                f"(na={config.na}, nb={config.nb}, nk={config.nk}, "
                f"{len(config.input_cols)} input channel(s))"
            )
        adapter = cls(train_config=config)
        adapter._theta = theta
        adapter._sigma2 = float(sigma2_raw) if sigma2_raw is not None else float("nan")

        # Map pipeline RMSE/MAE/R2 keys to adapter-convention lowercase keys
        train_m_raw: dict[str, Any] = (
            data.get("slices", {}).get("train", {}).get("metrics_1step", {})
        )
        if train_m_raw:
            adapter._train_metrics = {
                "rmse": float(train_m_raw.get("RMSE", float("nan"))),
                "mae": float(train_m_raw.get("MAE", float("nan"))),
                "r2": float(train_m_raw.get("R2", float("nan"))),
            }
        if val_m_raw:
            adapter._val_metrics = {
                "rmse": float(val_m_raw.get("RMSE", float("nan"))),
                "mae": float(val_m_raw.get("MAE", float("nan"))),
                "r2": float(val_m_raw.get("R2", float("nan"))),
            }
        return adapter
