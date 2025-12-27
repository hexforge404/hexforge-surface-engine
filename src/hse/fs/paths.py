from __future__ import annotations

import os
from pathlib import Path

# Where job folders live on disk (mounted volume in compose)
SURFACE_OUTPUT_DIR = Path(os.getenv("SURFACE_OUTPUT_DIR", "/data/hexforge3d/surface"))

# Public URL prefix for assets (nginx will serve this)
SURFACE_PUBLIC_PREFIX = os.getenv("SURFACE_PUBLIC_PREFIX", "/assets/surface")


def job_dir(job_id: str) -> Path:
    return SURFACE_OUTPUT_DIR / job_id


def assets_root(job_id: str) -> Path:
    # Root folder containing everything for the job
    return job_dir(job_id)


def manifest_path(job_id: str) -> Path:
    # Manifest file stored alongside job assets
    return job_dir(job_id) / "job_manifest.json"


def job_json_path(job_id: str) -> Path:
    # Raw request payload / job config captured at submit time
    return job_dir(job_id) / "job.json"


__all__ = [
    "SURFACE_OUTPUT_DIR",
    "SURFACE_PUBLIC_PREFIX",
    "job_dir",
    "assets_root",
    "manifest_path",
    "job_json_path",
]
