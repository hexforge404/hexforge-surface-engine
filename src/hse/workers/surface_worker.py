from pathlib import Path
import time
from typing import Optional

from hse.fs.paths import job_dir
from hse.fs.writer import write_surface_job_json
from hse.contracts.envelopes import now_iso


def run_surface_job(job_id: str, subfolder: Optional[str] = None) -> None:
    """
    Minimal worker loop:
    - marks job running
    - simulates work
    - writes output folders
    """

    root = job_dir(job_id, subfolder=subfolder)
    created_at = now_iso()

    # Mark running
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="running",
        created_at=created_at,
        updated_at=now_iso(),
        params={},
        artifacts={},
    )

    # --- simulate real work ---
    time.sleep(2)

    # Create expected output dirs
    (root / "textures").mkdir(parents=True, exist_ok=True)
    (root / "enclosure").mkdir(parents=True, exist_ok=True)
    (root / "previews").mkdir(parents=True, exist_ok=True)

    # Touch hero preview (this flips status → complete)
    # Write non-empty placeholder outputs so status can become "complete"
    (root / "previews" / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header bytes
    (root / "enclosure" / "enclosure.stl").write_text("solid dummy\nendsolid dummy\n", encoding="utf-8")
    (root / "textures" / "texture.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "textures" / "heightmap.png").write_bytes(b"\x89PNG\r\n\x1a\n")


    # Final status write
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="complete",
        created_at=created_at,
        updated_at=now_iso(),
        params={},
        artifacts={},
    )
