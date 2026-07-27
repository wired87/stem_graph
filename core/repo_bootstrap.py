"""
Prompt: ensure repo root on sys.path when modules run as ``python path/to/file.py``.

CHAR: inline copy in script entrypoints avoids import-before-path chicken-and-egg.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_repo_root(*, file: str, chdir: bool = True) -> Path:
    """Walk parents until acid_master root (core/ + embedder/) and prepend sys.path."""
    start = Path(file).resolve()
    script_dir = str(start.parent)
    for parent in start.parents:
        if (parent / "core").is_dir() and (parent / "embedder").is_dir():
            root_s = str(parent)
            # CHAR: repo root must precede script dir or ``tissue.*`` imports shadow packages.
            if root_s in sys.path:
                sys.path.remove(root_s)
            sys.path.insert(0, root_s)
            if script_dir in sys.path and script_dir != root_s:
                sys.path.remove(script_dir)
            if chdir and Path.cwd() != parent:
                try:
                    os.chdir(parent)
                except OSError:
                    pass
            return parent
    return start.parent


def inline_bootstrap_snippet() -> str:
    """Minimal snippet duplicated at top of script-runnable pipeline modules."""
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "_script_dir = str(Path(__file__).resolve().parent)\n"
        "for _p in Path(__file__).resolve().parents:\n"
        '    if (_p / "core").is_dir() and (_p / "embedder").is_dir():\n'
        "        _root = str(_p)\n"
        "        if _root in sys.path:\n"
        "            sys.path.remove(_root)\n"
        "        sys.path.insert(0, _root)\n"
        "        if _script_dir in sys.path and _script_dir != _root:\n"
        "            sys.path.remove(_script_dir)\n"
        "        break\n"
    )
