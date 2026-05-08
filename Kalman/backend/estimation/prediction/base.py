"""
Hợp đồng prediction adapter cho pipeline ước lượng Adaptive Kalman.

Bất kỳ model nào sinh dự đoán ``Soil_Moisture`` bước kế tiếp đều phải implement
``PredictionAdapter``. Baseline ARX nằm trong ``arx_adapter.py``; các adapter
LightGBM / XGBoost sau này cũng đi qua cùng boundary này để bộ Kalman
(task #005) không phụ thuộc vào chi tiết nội bộ của model.

Ràng buộc thiết kế
------------------
- ``predict()`` không được raise: dùng ``status="error"`` hoặc
  ``"unavailable"`` để chu kỳ Kalman vẫn chạy tiếp khi không có dự đoán.
- Các giá trị số trong ``PredictionInput.history`` được kỳ vọng là khác
  ``None``; preprocessor ở task #003 chịu trách nhiệm điền trước đó.
- ``model_kind`` là định danh ngắn, chữ thường như ``"arx"``, ``"lightgbm"``,
  được lưu cùng từng dòng log chu kỳ để truy vết.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from ..ingestion import ProcessedRecord


@dataclass
class PredictionInput:
    """Cửa sổ record đã tiền xử lý, dùng để dự đoán trước 1 bước.

    Các record phải theo thứ tự thời gian, cũ nhất trước. Các field thực tế
    nên khác ``None``; preprocessor phải xử lý thay thế trước khi gọi
    ``predict()``.

    Attributes
    ----------
    history:
        Cần ít nhất ``adapter.min_history_len`` record.
    """

    history: list[ProcessedRecord] = field(default_factory=list)


@dataclass(frozen=True)
class PredictionResult:
    """Kết quả của một lần dự đoán trước 1 bước.

    Attributes
    ----------
    value:
        Giá trị ``Soil_Moisture`` dự đoán cho bước kế tiếp; ``None`` nếu không có.
    status:
        ``"ok"``: dự đoán thành công.
        ``"unavailable"``: model chưa train hoặc thiếu history.
        ``"error"``: tính toán lỗi; chi tiết nằm trong ``reason``.
    model_kind:
        Định danh ngắn khớp với ``PredictionAdapter.model_kind``.
    reason:
        Giải thích dạng dễ đọc khi ``status != "ok"``.
    """

    value: float | None
    status: str
    model_kind: str
    reason: str = ""


class PredictionAdapter(ABC):
    """Abstract base cho mọi model dự đoán trong pipeline ước lượng.

    Implement class này để bọc một model cụ thể phía sau boundary mà bộ Kalman
    gọi. Hợp đồng này giấu chi tiết nội bộ của model, nhờ đó có thể thay adapter
    mà không phải sửa estimator.

    Thuộc tính và method bắt buộc
    -----------------------------
    model_kind        — định danh chữ thường, ví dụ ``"arx"``
    is_trained        — ``True`` khi model đã fit và sẵn sàng dự đoán
    min_history_len   — số record trước đó tối thiểu mà ``predict()`` cần
    predict()         — dự đoán trước 1 bước; không được raise
    load_artifact()   — classmethod; khôi phục adapter đã lưu
    """

    @property
    @abstractmethod
    def model_kind(self) -> str:
        """Định danh ngắn, chữ thường cho họ model, ví dụ ``"arx"``."""

    @property
    @abstractmethod
    def is_trained(self) -> bool:
        """``True`` khi adapter đang giữ model đã fit và sẵn sàng dự đoán."""

    @property
    @abstractmethod
    def min_history_len(self) -> int:
        """Số record trước đó tối thiểu cần có để gọi ``predict()``."""

    @abstractmethod
    def predict(self, inp: PredictionInput) -> PredictionResult:
        """Trả về dự đoán trước 1 bước từ history gần nhất.

        **Không được raise**. Nếu có lỗi, trả ``status="error"`` hoặc
        ``status="unavailable"`` để chu kỳ Kalman có thể chạy tiếp mà không
        cần dự đoán.

        Parameters
        ----------
        inp:
            History gần nhất; phải có ít nhất ``min_history_len`` record.

        Returns
        -------
        PredictionResult
            Luôn là object hợp lệ; cần kiểm tra ``status`` trước khi dùng ``value``.
        """

    @classmethod
    @abstractmethod
    def load_artifact(cls, path: Path) -> "PredictionAdapter":
        """Khôi phục adapter đã lưu từ *path*.

        Raises
        ------
        FileNotFoundError
            Nếu *path* không tồn tại.
        ValueError
            Nếu format artifact không nhận diện được.
        """
