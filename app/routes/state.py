"""
IncidentOps - Shared Application State

Holds globals shared between main.py and route modules.
Avoids circular imports when route files need access to app-level state.
"""
from typing import Optional

# WebSocket manager (initialized in main.py)
ws_manager: Optional["ConnectionManager"] = None  # type: ignore[name-defined]

# Prometheus metrics — detect at import time so route modules get correct value
try:
    from prometheus_client import Counter, Gauge
    _metrics_enabled: bool = True
except ImportError:
    _metrics_enabled = False

episodes_total = None  # Counter | None
episode_score = None   # Gauge | None
