"""
RunConfig là object cấu hình trong bộ nhớ cho một experiment run.

Thiết kế
--------
``RunConfig`` là nguồn sự thật chính cho mọi tham số có thể tune. Nó validate
tất cả field khi khởi tạo và giao việc tạo sub-config cho các dataclass đã có
validate sẵn như ``KalmanConfig`` và ``ARXTrainConfig``.

Khi run không còn trạng thái ``"pending"``, cấu hình bị khóa bởi tầng service
(xem ``service.py``). Không có cơ chế mutate trực tiếp trong process.

Vòng đời JSON
-------------
``RunConfig.to_json()`` / ``RunConfig.from_json()`` được dùng để ghi
``ExperimentConfig.raw_config_json``. Nhờ vậy một dòng đã lưu tự mô tả đầy đủ
và có thể tái tạo đúng cấu hình mà không cần đọc lại từng cột riêng lẻ.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from ..kalman.cycle import KalmanConfig
from ..prediction.arx_adapter import ARXTrainConfig, _DEFAULT_INPUT_COLS

# ── Chốt quyền chỉnh config ở v1 ──────────────────────────────────────────────
#
# Ràng buộc v1: không cho đổi cấu hình khi run không còn trạng thái "pending".
# Điều này được enforce ở tầng service (service.py). v1 chưa có phân quyền theo
# role; ràng buộc này được ghi lại như một invariant cứng của service từ
# Task #007 trở đi.

_IMMUTABLE_AFTER_START_NOTE = (
    "RunConfig is immutable after ExperimentRun.status moves out of 'pending'. "
    "Any mutation attempt via the service layer raises ConfigFrozenError."
)


class ConfigFrozenError(RuntimeError):
    """Raise khi cố sửa config sau khi run đã bắt đầu."""


# ── Hằng số ──────────────────────────────────────────────────────────────────

_VALID_PREPROCESS_POLICIES = frozenset({"keep_last", "interpolate", "skip"})


# ── Dataclass RunConfig ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunConfig:
    """Snapshot cấu hình dạng frozen cho một lần chạy ước lượng.

    Tất cả giá trị mặc định khớp với quyết định đã chốt ở ADR-003 (Task #001).

    Dataclass này frozen để object ``RunConfig`` không bị mutate sau khi tạo.
    Nếu cần đổi cấu hình trước khi run bắt đầu, tầng service sẽ tạo instance mới.

    Parameters
    ----------
    name:
        Tên dễ đọc cho run.
    dataset_source:
        Đường dẫn CSV hoặc mô tả bảng/query MySQL. Dùng để truy vết nguồn dữ liệu.

    Các field Kalman, validate qua ``KalmanConfig``
    ------------------------------------------------
    x0, P0, Q, R0, R_min, R_max, alpha

    Tỷ lệ chia theo thời gian
    -------------------------
    train_ratio, val_ratio, test_ratio phải dương và tổng bằng 1.0.

    Các field ARX, validate qua ``ARXTrainConfig``
    ----------------------------------------------
    arx_na, arx_nb, arx_nk
    arx_input_cols là tuple tên cột lấy từ field map của ARX.

    Tiền xử lý
    ----------
    preprocessing_policy là một trong "keep_last", "interpolate", "skip".
    """

    # Metadata của run
    name: str = "unnamed_run"
    dataset_source: str = ""

    # ── Tham số Kalman ────────────────────────────────────────────────────────
    x0: float = 0.0
    P0: float = 1.0
    Q: float = 0.05
    R0: float = 1.0
    R_min: float = 0.05
    R_max: float = 25.0
    alpha: float = 0.95

    # ── Tỷ lệ chia tập dữ liệu ────────────────────────────────────────────────
    train_ratio: float = 0.60
    val_ratio: float = 0.20
    test_ratio: float = 0.20

    # ── Bậc model ARX ─────────────────────────────────────────────────────────
    arx_na: int = 2
    arx_nb: int = 2
    arx_nk: int = 1
    arx_input_cols: tuple[str, ...] = field(default=_DEFAULT_INPUT_COLS)

    # ── Tiền xử lý ────────────────────────────────────────────────────────────
    preprocessing_policy: str = "keep_last"

    # ── Validate ──────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # Ép arx_input_cols về tuple bất biến dù caller truyền list, generator...
        # Vì dataclass frozen nên phải dùng object.__setattr__; gán trực tiếp sẽ
        # raise FrozenInstanceError.
        try:
            arx_input_cols = tuple(self.arx_input_cols)
        except TypeError as exc:
            raise ValueError(
                "arx_input_cols must be an iterable of column names"
            ) from exc
        object.__setattr__(self, "arx_input_cols", arx_input_cols)

        # Giao validate Kalman cho KalmanConfig để tái sử dụng các check đã có.
        KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

        # Tỷ lệ chia dữ liệu: mỗi tỷ lệ phải dương và tổng bằng 1.0.
        for _name, _val in (
            ("train_ratio", self.train_ratio),
            ("val_ratio", self.val_ratio),
            ("test_ratio", self.test_ratio),
        ):
            if not math.isfinite(_val) or _val <= 0.0:
                raise ValueError(f"{_name} must be a positive finite float, got {_val!r}")
        _total = self.train_ratio + self.val_ratio + self.test_ratio
        if not math.isclose(_total, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"train_ratio + val_ratio + test_ratio must sum to 1.0, "
                f"got {_total!r}"
            )

        # Validate ARX bằng ARXTrainConfig.
        ARXTrainConfig(
            na=self.arx_na,
            nb=self.arx_nb,
            nk=self.arx_nk,
            input_cols=self.arx_input_cols,
        )

        # Chính sách tiền xử lý.
        if self.preprocessing_policy not in _VALID_PREPROCESS_POLICIES:
            raise ValueError(
                f"preprocessing_policy must be one of {sorted(_VALID_PREPROCESS_POLICIES)}, "
                f"got {self.preprocessing_policy!r}"
            )

    # ── Trích sub-config ─────────────────────────────────────────────────────

    def to_kalman_config(self) -> KalmanConfig:
        """Trả về ``KalmanConfig`` tương ứng với tham số Kalman của run này."""
        return KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

    def to_arx_train_config(self) -> ARXTrainConfig:
        """Trả về ``ARXTrainConfig`` tương ứng với tham số ARX của run này."""
        return ARXTrainConfig(
            na=self.arx_na,
            nb=self.arx_nb,
            nk=self.arx_nk,
            input_cols=self.arx_input_cols,
        )

    # ── Serialize JSON ───────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialize thành chuỗi JSON để ghi vào ``ExperimentConfig.raw_config_json``."""
        d = asdict(self)
        # Tuple không serialize trực tiếp sang JSON được, nên đổi sang list.
        d["arx_input_cols"] = list(d["arx_input_cols"])
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "RunConfig":
        """Deserialize từ ``ExperimentConfig.raw_config_json``.

        Raise ``ValueError`` nếu payload thiếu field bắt buộc hoặc có giá trị
        không hợp lệ.
        """
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for RunConfig: {exc}") from exc
        if not isinstance(d, dict):
            raise ValueError("RunConfig JSON must be an object")
        try:
            return cls(**d)
        except TypeError as exc:
            raise ValueError(f"RunConfig JSON has unexpected fields: {exc}") from exc

    # ── Vòng đời ORM ─────────────────────────────────────────────────────────

    @classmethod
    def from_experiment_config(cls, db_row: object) -> "RunConfig":
        """Dựng lại ``RunConfig`` từ một dòng ORM ``ExperimentConfig``.

        Đọc các cột có cấu trúc thay vì chỉ đọc ``raw_config_json``, để kết quả
        vẫn là nguồn đáng tin kể cả khi snapshot JSON thuộc schema cũ. Nếu dòng
        được tạo trước khi có field ARX input_cols thì fallback về mặc định.
        """
        # arx_input_cols có thể không lưu trực tiếp trên Django model mà nằm
        # trong raw_config_json. Thử đọc JSON trước, nếu lỗi thì dùng mặc định.
        arx_cols: tuple[str, ...] = _DEFAULT_INPUT_COLS
        raw_json: str = getattr(db_row, "raw_config_json", "{}")
        try:
            parsed = json.loads(raw_json)
            if "arx_input_cols" in parsed:
                arx_cols = tuple(parsed["arx_input_cols"])
        except (json.JSONDecodeError, TypeError):
            pass

        run = getattr(db_row, "run", None)
        name: str = getattr(run, "name", "unnamed_run") if run is not None else "unnamed_run"
        dataset_source: str = (
            getattr(run, "dataset_source", "") or ""
            if run is not None
            else ""
        )

        return cls(
            name=name,
            dataset_source=dataset_source,
            x0=db_row.x0,  # type: ignore[union-attr]
            P0=db_row.P0,  # type: ignore[union-attr]
            Q=db_row.Q,  # type: ignore[union-attr]
            R0=db_row.R0,  # type: ignore[union-attr]
            R_min=db_row.R_min,  # type: ignore[union-attr]
            R_max=db_row.R_max,  # type: ignore[union-attr]
            alpha=db_row.alpha,  # type: ignore[union-attr]
            train_ratio=db_row.train_ratio,  # type: ignore[union-attr]
            val_ratio=db_row.val_ratio,  # type: ignore[union-attr]
            test_ratio=db_row.test_ratio,  # type: ignore[union-attr]
            arx_na=db_row.arx_na,  # type: ignore[union-attr]
            arx_nb=db_row.arx_nb,  # type: ignore[union-attr]
            arx_nk=db_row.arx_nk,  # type: ignore[union-attr]
            arx_input_cols=arx_cols,
            preprocessing_policy=db_row.preprocessing_policy,  # type: ignore[union-attr]
        )
