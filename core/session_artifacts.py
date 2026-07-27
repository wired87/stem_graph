"""
Session artifact helpers — optional 2D scan persistence and zip bundling for MCP output.

Prompt (user): Make this project a production ready system. Include test files if
needed inside a tests directory.

CHAR: kept free of FastMCP so unit tests and lightweight CI do not require Python 3.10+
transitive stacks from the MCP server layer.
"""
from __future__ import annotations

import uuid
import zipfile
from pathlib import Path, PurePath
from tempfile import gettempdir
# CHAR: zipped bundles for MCP clients — one zip per generation session.
_SESSION_ZIP_DIR = Path(gettempdir()) / "acid_master_session_zips"


def persist_scan_in_session(session_dir: Path, file_bytes: bytes, original_filename: str) -> str:
    """
    Write optional 2D scan into ``session_dir`` and return absolute path for
    ``UniprotKB.main(..., scan_path=...)``.
    """
    raw_name = (original_filename or "").strip()
    if not raw_name:
        raise ValueError("scan_2d_filename must be a non-empty basename (no path segments).")
    # CHAR: reject any path separators so clients cannot escape the session directory.
    if PurePath(raw_name).name != raw_name or "/" in raw_name or "\\" in raw_name:
        raise ValueError("scan_2d_filename must be a single basename (no path segments).")
    base = PurePath(raw_name).name.strip()
    if not base or base in (".", ".."):
        raise ValueError("scan_2d_filename must be a non-empty basename (no path segments).")
    if not Path(base).suffix:
        raise ValueError(
            "scan_2d_filename must include a supported extension for data.scan.ScanIngestionLayer "
            "(e.g. .dcm, .nii, .nii.gz, .png, .tif, .jpg)."
        )
    session_dir.mkdir(parents=True, exist_ok=True)
    dest = session_dir / base
    if dest.exists():
        dest = session_dir / f"{uuid.uuid4().hex}_{base}"
    dest.write_bytes(file_bytes)
    return str(dest.resolve())


def zip_session_artifacts(
    session_id: str,
    paths: list[str | None],
    *,
    zip_root: Path | None = None,
) -> str:
    """
    Pack existing files into ``<zip_root>/<session_id>.zip`` (flat tree per session).

    When ``zip_root`` is omitted, uses the host temp directory
    ``acid_master_session_zips`` (see module constant).
    """
    root = _SESSION_ZIP_DIR if zip_root is None else zip_root
    root.mkdir(parents=True, exist_ok=True)
    zip_path = root / f"{session_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if not p:
                continue
            pp = Path(p)
            if not pp.is_file():
                continue
            arc = f"{session_id}/{pp.name}"
            zf.write(pp, arcname=arc)
    return str(zip_path.resolve())
