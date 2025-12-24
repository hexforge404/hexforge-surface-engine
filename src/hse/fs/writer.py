import json
from pathlib import Path
from typing import Any, Dict

def ensure_dirs(job_root: Path) -> None:
    (job_root / "textures").mkdir(parents=True, exist_ok=True)
    (job_root / "enclosure").mkdir(parents=True, exist_ok=True)
    (job_root / "previews").mkdir(parents=True, exist_ok=True)

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
