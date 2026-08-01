"""Discover template roots without scanning data, output, or nested repositories."""
from __future__ import annotations

from pathlib import Path


def _html_directories(root: Path) -> set[Path]:
    return {
        path.parent.resolve()
        for pattern in ("*.html", "*.htm")
        for path in root.rglob(pattern)
        if path.is_file()
    } if root.is_dir() else set()


def extract_template_dirs(base_dir: str | Path) -> list[Path]:
    """Inspect only the project template tree and Django app template/component trees."""
    root = Path(base_dir).resolve()
    search_roots = [root / "templates"]
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "apps.py").is_file() or (child / "components").is_dir():
            search_roots.extend((child / "templates", child / "components"))
    found: set[Path] = set()
    for search_root in search_roots:
        found.update(_html_directories(search_root))
    return sorted(found, key=lambda path: path.as_posix().lower())
