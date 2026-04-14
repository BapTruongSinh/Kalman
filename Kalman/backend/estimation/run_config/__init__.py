"""
``estimation.run_config`` — experiment configuration persistence.

Public API
----------
``RunConfig``         — frozen in-memory configuration object (validated at creation)
``ConfigFrozenError`` — raised when config mutation is attempted after run start
``create_run``        — atomically persist RunConfig as ExperimentRun + ExperimentConfig
``load_config``       — reconstruct RunConfig from a saved run id
``update_config``     — replace a pending run's config (raises ConfigFrozenError otherwise)
"""

from .config import ConfigFrozenError, RunConfig
from .service import create_run, load_config, update_config

__all__ = [
    "RunConfig",
    "ConfigFrozenError",
    "create_run",
    "load_config",
    "update_config",
]
