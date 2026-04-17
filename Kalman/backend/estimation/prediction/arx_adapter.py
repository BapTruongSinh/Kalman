"""
ARX prediction adapter, bọc ``arx_pipeline.py`` phía sau ``PredictionAdapter``.

Module này cung cấp ``ARXPredictionAdapter``, model dự đoán baseline của v1.
Nó tái hiện logic train OLS và dự đoán trước 1 bước từ ``arx_pipeline.py``,
nhưng chỉ dùng NumPy và object ``ProcessedRecord`` để không import code kiểu
notebook khi chạy backend.

``load_artifact()`` hỗ trợ hai format artifact:

- **Native format** do ``save_artifact()`` ghi ra, có key ``"adapter_version"``.
- **Pipeline format** do ``arx_pipeline.save_artifact()`` ghi ra, có
  ``model="ARX"`` và cấu trúc ``model_config`` / ``theta_hat`` từ pipeline
  notebook hiện có. Nếu có ``best_candidate`` thì ưu tiên dùng nó.

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

# ── Ánh xạ field ─────────────────────────────────────────────────────────────
# Tên attribute của ProcessedRecord → tên cột DataFrame / ARX.
_FIELD_MAP: dict[str, str] = {
    "soil_moisture": "Soil_Moisture",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "light": "Light",
    "drip": "Drip",
    "mist": "Mist",
    "fan": "Fan",
}

# Tên cột ARX → tên attribute của ProcessedRecord (đảo ngược từ _FIELD_MAP).
_COL_TO_ATTR: dict[str, str] = {v: k for k, v in _FIELD_MAP.items()}

_DEFAULT_INPUT_COLS: tuple[str, ...] = (
    "Temperature",
    "Humidity",
    "Light",
    "Drip",
    "Mist",
    "Fan",
)


# ── Cấu hình ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ARXTrainConfig:
    """Các siêu tham số để train model ARX offline.

    Attributes
    ----------
    na:
        Bậc AR, tức số thành phần output trễ.
    nb:
        Bậc input ngoại sinh, tức số thành phần input trễ trên mỗi kênh.
    nk:
        Độ trễ input (dead-time). ``nk=1`` nghĩa là không có dead-time ngoài
        một bước trễ cơ bản.
    include_intercept:
        Có thêm hệ số chặn vào hồi quy hay không.
    input_cols:
        Tuple có thứ tự của tên cột ARX/DataFrame, ví dụ ``"Temperature"``,
        ``"Humidity"``. Phải nằm trong các *value* của ``_FIELD_MAP``.
    output_col:
        Tên cột output, ví dụ ``"Soil_Moisture"``. Phải là một *value* trong
        ``_FIELD_MAP``.
    """

    na: int = 2
    nb: int = 2
    nk: int = 1
    include_intercept: bool = False
    input_cols: tuple[str, ...] = _DEFAULT_INPUT_COLS
    output_col: str = "Soil_Moisture"

    def __post_init__(self) -> None:
        """Validate siêu tham số ngay khi tạo object."""
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
        """Chỉ số lag lớn nhất cần để xây một dòng hồi quy."""
        return max(self.na, self.nb + self.nk - 1)

    @property
    def min_history_len(self) -> int:
        """Kích thước history tối thiểu để dự đoán trước 1 bước."""
        return self.max_lag

    def param_names(self) -> list[str]:
        """Trả về tên tham số theo đúng thứ tự của ``theta_hat``."""
        names = [f"a{lag}" for lag in range(1, self.na + 1)]
        for col in self.input_cols:
            for lag in range(1, self.nb + 1):
                names.append(f"b_{col}_{lag}")
        if self.include_intercept:
            names.append("intercept")
        return names

    def n_params(self) -> int:
        return len(self.param_names())


# ── Helper tính toán nội bộ ──────────────────────────────────────────────────


def _records_to_arrays(
    records: Sequence[ProcessedRecord],
    config: ARXTrainConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Chuyển chuỗi ``ProcessedRecord`` thành ma trận hồi quy OLS.

    Tương đương ``arx_pipeline.build_regression_matrix`` nhưng làm trực tiếp
    trên object ``ProcessedRecord``, không cần phụ thuộc pandas.

    Returns
    -------
    x_mat : np.ndarray, shape ``(n_eff, n_params)``
    y_vec : np.ndarray, shape ``(n_eff,)``

    Raises
    ------
    ValueError
        Nếu không đủ record cho bậc trễ đã cấu hình.
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
        # Phần AR: output trễ.
        for lag in range(1, config.na + 1):
            row.append(float(y[t - lag]))
        # Phần ngoại sinh: input trễ có xét dead-time nk.
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
    """Xây vector hồi quy cho một lần dự đoán trước 1 bước.

    Dùng ``config.min_history_len`` record gần nhất trong *history* bằng
    negative indexing, nên các record cũ hơn sẽ bị bỏ qua.

    Parameters
    ----------
    history:
        Ít nhất ``config.min_history_len`` record, theo thứ tự thời gian.
    config:
        Phải khớp với config đã dùng khi train.

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
    # Phần AR: na giá trị output gần nhất (lag 1 = mới nhất).
    for lag in range(1, config.na + 1):
        row.append(float(y[-lag]))
    # Phần ngoại sinh: input gần nhất có xét dead-time nk.
    for u in input_arrays:
        for lag in range(config.nk, config.nk + config.nb):
            row.append(float(u[-lag]))
    if config.include_intercept:
        row.append(1.0)

    return np.array(row, dtype=float)


def _ols_fit(
    x_mat: np.ndarray, y_vec: np.ndarray
) -> tuple[np.ndarray, float]:
    """Fit Ordinary Least Squares.

    Returns
    -------
    theta : np.ndarray, shape ``(n_params,)``
    sigma2 : float — ước lượng phương sai phần dư
    """
    theta, _, _, _ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    n_obs, n_params = x_mat.shape
    resid = y_vec - x_mat @ theta
    sigma2 = float(np.dot(resid, resid) / max(1, n_obs - n_params))
    return theta, sigma2


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Tính RMSE, MAE và R² giữa *y_true* và *y_pred*."""
    resid = y_true - y_pred
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    mae = float(np.mean(np.abs(resid)))
    ss_res = float(np.dot(resid, resid))
    ss_tot = float(np.dot(y_true - y_true.mean(), y_true - y_true.mean()))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0.0 else float("nan")
    return {"rmse": rmse, "mae": mae, "r2": r2}


# ── Adapter ───────────────────────────────────────────────────────────────────


class ARXPredictionAdapter(PredictionAdapter):
    """Prediction adapter baseline dùng ARX.

    Bọc việc train OLS offline và dự đoán trước 1 bước phía sau hợp đồng
    ``PredictionAdapter``. Không import code tầng notebook.

    Lifecycle
    ---------
    1. **Train**: ``adapter.train(train_records, val_records=val_records)``
    2. **Persist**: ``adapter.save_artifact(path)``
    3. **Reload**: ``ARXPredictionAdapter.load_artifact(path)``
    4. **Predict**: ``adapter.predict(PredictionInput(history=recent))``

    Load ``arx_model.json``
    -----------------------
    ``load_artifact()`` nhận cả native format do ``save_artifact()`` ghi ra
    *và* format do ``arx_pipeline.save_artifact()`` hiện có ghi ra
    (từ ``../ARX/arx_pipeline.py``). Nếu pipeline artifact có
    ``"best_candidate"``, adapter ưu tiên dùng ``model_config`` và
    ``theta_hat`` của candidate đó.
    """

    _KIND = "arx"

    def __init__(self, train_config: ARXTrainConfig | None = None) -> None:
        self._config: ARXTrainConfig = train_config or ARXTrainConfig()
        self._theta: np.ndarray | None = None
        self._sigma2: float | None = None
        self._train_metrics: dict[str, float] | None = None
        self._val_metrics: dict[str, float] | None = None

    # ── Interface PredictionAdapter ────────────────────────────────────────

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
        """Trả về cấu hình siêu tham số ARX."""
        return self._config

    @property
    def train_metrics(self) -> dict[str, float] | None:
        """Metric trên tập train sau ``train()``, nếu chưa có thì ``None``."""
        return dict(self._train_metrics) if self._train_metrics else None

    @property
    def val_metrics(self) -> dict[str, float] | None:
        """Metric trên tập validation sau ``train(val_records=...)``, nếu chưa có thì ``None``."""
        return dict(self._val_metrics) if self._val_metrics else None

    # ── Train ─────────────────────────────────────────────────────────────

    def train(
        self,
        records: Sequence[ProcessedRecord],
        *,
        val_records: Sequence[ProcessedRecord] | None = None,
    ) -> dict[str, object]:
        """Train OLS offline trên *records*.

        Parameters
        ----------
        records:
            Record train theo thứ tự thời gian.
        val_records:
            Record hold-out tùy chọn để báo cáo metric validation.

        Returns
        -------
        dict
            Tóm tắt gồm các key: ``model_kind``, ``na``, ``nb``, ``nk``,
            ``n_params``, ``n_train``, ``sigma2``, ``train_metrics``, and
            optionally ``n_val`` / ``val_metrics``.

        Raises
        ------
        ValueError
            Nếu *records* quá ngắn so với bậc trễ đã cấu hình.
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

    # ── Dự đoán ──────────────────────────────────────────────────────────

    def predict(self, inp: PredictionInput) -> PredictionResult:
        """Dự đoán ``Soil_Moisture`` trước 1 bước từ history gần nhất.

        Trả ``status="unavailable"`` thay vì exception khi model chưa train
        hoặc history quá ngắn. Trả ``status="error"`` nếu tính toán số bị lỗi.

        Method này **không bao giờ raise**; mọi nhánh lỗi đều trả
        ``PredictionResult`` với ``status`` và ``reason`` phù hợp.

        Parameters
        ----------
        inp:
            Phải có ít nhất ``min_history_len`` record. Các field phải khác
            ``None`` (được preprocessor điền trước khi gọi predict). Nếu truyền
            ``None`` hoặc object sai dạng thì trả ``status="error"``.

        Returns
        -------
        PredictionResult
            Cần kiểm tra ``status`` trước khi dùng ``value``.
        """
        # ── Chặn input lỗi ────────────────────────────────────────────────────
        # Lấy history và độ dài trước mọi logic khác, để inp None, history None,
        # hoặc history không phải sequence không biến thành exception chưa xử lý.
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
            # Xác định các attribute ProcessedRecord bắt buộc phải có.
            out_attr = _COL_TO_ATTR.get(self._config.output_col, "soil_moisture")
            input_attrs = [
                _COL_TO_ATTR.get(col, col.lower())
                for col in self._config.input_cols
            ]
            required_attrs = [out_attr] + input_attrs

            # Kiểm tra giá trị None trong các field bắt buộc của record gần nhất.
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

    # ── Lưu / nạp artifact ────────────────────────────────────────────────

    def save_artifact(self, path: Path) -> None:
        """Lưu model đã train thành JSON artifact.

        File ghi ra dùng *native* format mà ``load_artifact()`` hiểu được.
        File cũng chứa đủ thông tin để con người dựng lại model thủ công.

        Raises
        ------
        RuntimeError
            Nếu model chưa được train.
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
        """Khôi phục adapter đã train từ JSON artifact.

        Supports two formats:

        - **Native** (có key ``"adapter_version"``): do ``save_artifact()`` ghi.
        - **Pipeline** (``model="ARX"`` + ``"model_config"``): do
          ``arx_pipeline.save_artifact()`` hiện có ghi; nếu có
          ``"best_candidate"`` thì dùng config và theta của nó.

        Raises
        ------
        FileNotFoundError
            Nếu *path* không tồn tại.
        ValueError
            Nếu format artifact không nhận diện được.
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

    # ── Hàm nạp nội bộ ────────────────────────────────────────────────────

    @classmethod
    def _load_native(cls, data: dict[str, Any]) -> "ARXPredictionAdapter":
        """Nạp artifact theo native adapter format."""
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
        """Nạp từ format của ``arx_pipeline.save_artifact()``.

        Nếu có thì dùng config, theta **và sigma2** của ``best_candidate``;
        nếu không thì fallback về ``model_config`` / ``theta_hat`` /
        ``sigma2`` ở top-level.
        """
        top_cfg_d: dict[str, Any] = data["model_config"]
        best_used = "best_candidate" in data and "theta_hat" in data["best_candidate"]

        if best_used:
            best: dict[str, Any] = data["best_candidate"]
            cfg_d: dict[str, Any] = best.get("model_config", top_cfg_d)
            theta_list: list[float] = best["theta_hat"]
            # Dùng sigma2 của best_candidate để nhất quán với theta đã chọn.
            sigma2_raw = best.get("sigma2")
            # Lấy metric validation từ best_candidate.val.
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

        # Map key RMSE/MAE/R2 của pipeline sang key chữ thường theo adapter.
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
