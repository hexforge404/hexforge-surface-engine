from __future__ import annotations

import os
from pathlib import Path


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
    """
    return os.getenv("SURFACE_PUBLIC_PREFIX", "/assets/surface")


def public_root(job_id: str) -> str:
    """
    Public URL base for a given job.
    Example: /assets/surface/<job_id>
    """
    return f"{public_prefix().rstrip('/')}/{job_id}"


def job_dir(job_id: str) -> Path:
    return assets_root() / job_id


def manifest_path(job_id: str) -> Path:
    # keep filename stable across engines
    return job_dir(job_id) / "job_manifest.json"


def job_json_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


__all__ = [
    "assets_root",
    "public_prefix",
    "public_root",
    "job_dir",
    "manifest_path",
    "job_json_path",
]
