from __future__ import annotations

from pathlib import Path
from typing import Optional


SURFACE_ROOT = Path("/data/hexforge3d/surface")


def job_dir(job_id: str) -> Path:
    return SURFACE_ROOT / job_id


def public_root(job_id: str, subfolder: Optional[str] = None) -> str:
    # Contract: public URLs must be /assets/...
    # Keep trailing slash.
    if subfolder:
        return f"/assets/surface/{job_id}/{subfolder}/"
    return f"/assets/surface/{job_id}/"


def manifest_path(job_id: str) -> Path:
    return job_dir(job_id) / "job_manifest.json"
