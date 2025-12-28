from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

# Only allow a single safe folder name (no slashes, dots, whitespace, traversal)
_SUBFOLDER_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def sanitize_subfolder(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if not _SUBFOLDER_RE.match(v):
        return None
    return v


def assets_root() -> Path:
    """
    Root folder where engine writes job folders.
    Mounted in docker-compose as /data/hexforge3d and we use /data/hexforge3d/surface by default.
    """
    base = os.getenv("SURFACE_OUTPUT_DIR", "/data/hexforge3d/surface")
    return Path(base)


def public_prefix() -> str:
    """
    URL prefix where the public files are served from (nginx or media_api).
    Must remain a relative URL like /assets/surface (Surface v1 rule).
    """
    return os.getenv("SURFACE_PUBLIC_PREFIX", "/assets/surface").rstrip("/")


def job_dir(job_id: str, *, subfolder: Optional[str] = None) -> Path:
    sf = sanitize_subfolder(subfolder)
    if sf:
        return assets_root() / sf / job_id
    return assets_root() / job_id


def public_root(job_id: str, *, subfolder: Optional[str] = None) -> str:
    """
    Public URL base for a given job.
    Example: /assets/surface/<subfolder?>/<job_id>
    """
    sf = sanitize_subfolder(subfolder)
    if sf:
        return f"{public_prefix()}/{sf}/{job_id}"
    return f"{public_prefix()}/{job_id}"


def manifest_path(job_id: str, *, subfolder: Optional[str] = None) -> Path:
    # keep filename stable across engines
    return job_dir(job_id, subfolder=subfolder) / "job_manifest.json"


def job_json_path(job_id: str, *, subfolder: Optional[str] = None) -> Path:
    return job_dir(job_id, subfolder=subfolder) / "job.json"


__all__ = [
    "sanitize_subfolder",
    "assets_root",
    "public_prefix",
    "public_root",
    "job_dir",
    "manifest_path",
    "job_json_path",
]
