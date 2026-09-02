"""
DuckDB _db configuration.

Env vars:
- DUCK_DB_PATH: canonical DB file path (default: qbrain/local.duckdb)
- DUCK_DB_VERBOSE: 0=off, 1=ops, 2=debug
- DUCK_DB_LOG_LEVEL: optional logging level (INFO, DEBUG, WARNING)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cnvmaster.settings import BASE_DIR

_DEFAULT_DUCK_PATH = str(Path(__file__).resolve().parent.parent / "local.duckdb")


def duck_db_path() -> str:
    """Single canonical path for all processes (prod, test, CLI)."""
    default = Path(tempfile.gettempdir()) / "stemgraph" / "firegraph.duckdb"
    path = Path(os.environ.get("DUCK_DB_PATH", default))
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def duck_db_verbose() -> int:
    """0=off, 1=ops, 2=debug."""
    val = os.environ.get("DUCK_DB_VERBOSE", "0")
    try:
        return int(val)
    except ValueError:
        return 0


def duck_db_log_level() -> str:
    """Logging level for qbrain._db logger."""
    return os.environ.get("DUCK_DB_LOG_LEVEL", "INFO").upper()
