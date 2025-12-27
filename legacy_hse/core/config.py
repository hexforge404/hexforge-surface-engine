import os
from pathlib import Path

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v and v.strip() else default

# Host-mounted root in container
SURFACE_OUTPUT_DIR = Path(_env("SURFACE_OUTPUT_DIR", "/data/hexforge3d/surface"))
# Public URL prefix nginx serves from the same mount
SURFACE_PUBLIC_PREFIX = _env("SURFACE_PUBLIC_PREFIX", "/assets/surface")

def ensure_dirs() -> None:
    SURFACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
