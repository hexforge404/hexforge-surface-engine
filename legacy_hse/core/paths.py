import re
from pathlib import Path
from typing import Optional

SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")

def sanitize_subfolder(subfolder: Optional[str]) -> Optional[str]:
    if not subfolder:
        return None
    s = subfolder.strip()
    if not s:
        return None
    # allow only safe single folder names
    if not SAFE.match(s):
        return None
    return s

def job_root(output_dir: Path, job_id: str, subfolder: Optional[str]) -> Path:
    if not SAFE.match(job_id):
        raise ValueError("job_id must be filesystem-safe (a-zA-Z0-9._-)")
    sf = sanitize_subfolder(subfolder)
    return (output_dir / sf / job_id) if sf else (output_dir / job_id)

def ensure_job_tree(root: Path) -> dict:
    enc = root / "enclosure"
    tex = root / "textures"
    prev = root / "previews"
    enc.mkdir(parents=True, exist_ok=True)
    tex.mkdir(parents=True, exist_ok=True)
    prev.mkdir(parents=True, exist_ok=True)
    return {"root": root, "enclosure": enc, "textures": tex, "previews": prev}
