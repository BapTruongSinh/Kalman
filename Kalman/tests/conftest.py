"""Test path setup for running Kalman package tests from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

KALMAN_ROOT = Path(__file__).resolve().parents[1]
if str(KALMAN_ROOT) not in sys.path:
    sys.path.insert(0, str(KALMAN_ROOT))
