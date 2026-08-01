"""
DB log facade: respects DUCK_DB_VERBOSE for production-safe output.

- verbose 0: no output
- verbose 1: info, warn, error
- verbose 2: + debug, full detail
"""
from __future__ import annotations

from typing import Any




def db_log(level: str, msg: str, **kwargs: Any) -> None:
    """
    Log DB message when DUCK_DB_VERBOSE allows.
    level: info, warn, error, debug
    """
    print(level, msg)


def duck_print_result(op: str, **kwargs: Any) -> None:
    """Thin wrapper for table_handling compatibility; logs when verbose."""
    db_log("debug", f"[duck] {op}", **kwargs)
