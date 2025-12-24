import re
from pathlib import Path
from typing import Optional, Dict

from hse.config import PUBLIC_ASSETS_URL_ROOT, surface_assets_root

_SAFE_SUBFOLDER_RE = re.compile(r"^[A-Za-z0-9_-]+$")

def sanitize_subfolder(subfolder: Optional[str]) -> Optional[str]:
    """
    Rules (locked):
    - optional
    - if invalid, return None
    - allowed: letters, numbers, dash, underscore
    - forbidden: slashes, dots, traversal sequences
    """
    if not subfolder:
        return None
    subfolder = subfolder.strip()
    if not subfolder:
        return None
    if not _SAFE_SUBFOLDER_RE.match(subfolder):
        return None
    return subfolder

def job_disk_root(job_id: str, subfolder: Optional[str] = None) -> Path:
    """
    Returns the on-disk root folder for a job.
    /mnt/.../assets/surface/<subfolder?>/<job_id>/
    """
    sf = sanitize_subfolder(subfolder)
    base = surface_assets_root()
    return (base / sf / job_id).resolve() if sf else (base / job_id).resolve()

def job_public_root(job_id: str, subfolder: Optional[str] = None) -> str:
    """
    Returns the public URL root for a job.
    /assets/surface/<subfolder?>/<job_id>/
    """
    sf = sanitize_subfolder(subfolder)
    if sf:
        return f"{PUBLIC_ASSETS_URL_ROOT}/{sf}/{job_id}/"
    return f"{PUBLIC_ASSETS_URL_ROOT}/{job_id}/"

def public_paths(job_id: str, subfolder: Optional[str] = None) -> Dict[str, object]:
    """
    Locked response keys under result.public (matches INTERFACES.md):
    - root
    - enclosure.stl
    - enclosure.handoff
    - textures.texture_png
    - textures.heightmap_png
    - textures.heightmap_exr (optional, may be null later)
    - previews.hero / iso / top / side
    - job_json
    """
    root = job_public_root(job_id, subfolder)
    return {
        "root": root,
        "enclosure": {
            "stl": f"{root}enclosure/enclosure.stl",
            "handoff": f"{root}enclosure/enclosure.obj",
        },
        "textures": {
            "texture_png": f"{root}textures/texture.png",
            "heightmap_png": f"{root}textures/heightmap.png",
            "heightmap_exr": f"{root}textures/heightmap.exr",
        },
        "previews": {
            "hero": f"{root}previews/hero.png",
            "iso": f"{root}previews/iso.png",
            "top": f"{root}previews/top.png",
            "side": f"{root}previews/side.png",
        },
        "job_json": f"{root}job.json",
    }
