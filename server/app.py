#!/usr/bin/env python3
"""
IncidentOps Server Entry Point

This module provides the server entry point for multi-mode deployment.
It can be used as:
    - Direct: python -m server.app
    - Uvicorn: uvicorn server.app:app
    - Command: server (via [project.scripts] in pyproject.toml)
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app, main as _uvicorn_main


def main() -> None:
    """Main entry point for the server command."""
    _uvicorn_main()


if __name__ == "__main__":
    main()
