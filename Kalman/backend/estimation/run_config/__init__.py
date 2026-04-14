"""
``estimation.run_config`` — experiment configuration persistence.

Public API (no Django dependency at import time)
------------------------------------------------
``RunConfig``         — frozen in-memory configuration object (validated at creation)
``ConfigFrozenError`` — raised when config mutation is attempted after run start

DB-backed service functions (require Django / ``django.setup()``)
-----------------------------------------------------------------
``create_run``    — atomically persist RunConfig as ExperimentRun + ExperimentConfig
``load_config``   — reconstruct RunConfig from a saved run id
``update_config`` — replace a pending run's config (raises ConfigFrozenError otherwise)

These three names are available from this package but are loaded lazily so that
importing ``RunConfig`` alone never touches Django ORM code.  Callers that need
the full service layer can also import directly::

    from estimation.run_config.service import create_run, load_config, update_config
"""

from .config import ConfigFrozenError, RunConfig

__all__ = [
    "RunConfig",
    "ConfigFrozenError",
    "create_run",
    "load_config",
    "update_config",
]


def __getattr__(name: str) -> object:
    """Lazy-load service functions so that importing ``RunConfig`` alone never
    triggers Django ORM initialisation (``django.setup()`` is not required for
    pure-config use-cases).
    """
    if name in ("create_run", "load_config", "update_config"):
        from .service import create_run, load_config, update_config  # noqa: PLC0415

        # Cache on the module so subsequent attribute lookups are O(1) and don't
        # re-enter __getattr__.
        import sys as _sys

        _mod = _sys.modules[__name__]
        _mod.create_run = create_run  # type: ignore[attr-defined]
        _mod.load_config = load_config  # type: ignore[attr-defined]
        _mod.update_config = update_config  # type: ignore[attr-defined]

        return {"create_run": create_run, "load_config": load_config, "update_config": update_config}[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
