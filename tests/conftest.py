"""
IncidentOps - Pytest Configuration
"""
import os

# Disable/enable rate limiting during tests so integration tests don't get 429
# Must be set BEFORE importing app.main (which initializes slowapi at module level)
os.environ.setdefault("RATE_LIMIT", "10000/minute")
os.environ.setdefault("BASELINE_RATE_LIMIT", "10000/minute")
os.environ.setdefault("RESET_RATE_LIMIT", "10000/minute")
os.environ.setdefault("STEP_RATE_LIMIT", "10000/minute")
os.environ.setdefault("GRADER_RATE_LIMIT", "10000/minute")

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

pytest_plugins = ["pytest_asyncio"]
