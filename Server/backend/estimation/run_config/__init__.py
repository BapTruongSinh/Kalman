"""
``estimation.run_config``: lưu và khôi phục cấu hình experiment.

Public API, không phụ thuộc Django tại thời điểm import
-------------------------------------------------------
``RunConfig``         — object cấu hình trong bộ nhớ dạng frozen, validate khi tạo
``ConfigFrozenError`` — raise khi cố mutate config sau khi run đã bắt đầu

Các hàm service dùng DB, cần Django / ``django.setup()``
-------------------------------------------------------
``create_run``    — lưu RunConfig thành ExperimentRun + ExperimentConfig trong transaction
``load_config``   — dựng lại RunConfig từ run id đã lưu
``update_config`` — thay config của run còn pending; nếu không thì raise ConfigFrozenError

Ba tên này có sẵn từ package nhưng được load lazy, để chỉ import ``RunConfig``
thì không đụng tới Django ORM. Caller cần đầy đủ tầng service cũng có thể import
trực tiếp::

    from estimation.run_config.service import create_run, load_config, update_config
"""

from kalman.run_config import ConfigFrozenError, RunConfig

__all__ = [
    "RunConfig",
    "ConfigFrozenError",
    "create_run",
    "load_config",
    "update_config",
]


def __getattr__(name: str) -> object:
    """Load lazy các hàm service để import ``RunConfig`` không khởi tạo Django ORM.

    Nhờ vậy các use-case chỉ cần config thuần không phải gọi ``django.setup()``.
    """
    if name in ("create_run", "load_config", "update_config"):
        from .service import create_run, load_config, update_config  # noqa: PLC0415

        # Cache trên module để các lần lookup sau là O(1) và không đi lại vào
        # __getattr__.
        import sys as _sys

        _mod = _sys.modules[__name__]
        _mod.create_run = create_run  # type: ignore[attr-defined]
        _mod.load_config = load_config  # type: ignore[attr-defined]
        _mod.update_config = update_config  # type: ignore[attr-defined]

        return {"create_run": create_run, "load_config": load_config, "update_config": update_config}[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
