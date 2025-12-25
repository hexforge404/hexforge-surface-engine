import json
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw

from hse.core.config import SURFACE_OUTPUT_DIR, SURFACE_PUBLIC_PREFIX, ensure_dirs
from hse.core.paths import job_root, ensure_job_tree, sanitize_subfolder
from hse.schemas.jobs import CreateJobRequest, CreateJobResponse

router = APIRouter(prefix="/api/surface", tags=["surface"]) 

def _public_url(subfolder: str | None, job_id: str, rel: str) -> str:
    if subfolder:
        return f"{SURFACE_PUBLIC_PREFIX}/{subfolder}/{job_id}/{rel}"
    return f"{SURFACE_PUBLIC_PREFIX}/{job_id}/{rel}"

def _write_placeholder_png(path: Path, label: str, size=(768, 512)) -> None:
    img = Image.new("RGB", size, color=(15, 18, 28))
    d = ImageDraw.Draw(img)
    d.text((20, 20), label, fill=(220, 240, 255))
    img.save(path, format="PNG")

@router.get("/health")
def health():
    return {"ok": True, "service": "hexforge-glyphengine", "api": "surface-v1"}

@router.post("/jobs", response_model=CreateJobResponse)
def create_job(req: CreateJobRequest):
    ensure_dirs()
    job_id = uuid.uuid4().hex[:16]
    sf = sanitize_subfolder(req.subfolder)
    root = job_root(SURFACE_OUTPUT_DIR, job_id, sf)
    tree = ensure_job_tree(root)

    job_payload = {
        "job_id": job_id,
        "subfolder": sf,
        "created_at": int(time.time()),
        "request": req.model_dump(),
    }
    (tree["root"] / "job.json").write_text(json.dumps(job_payload, indent=2))

    # placeholders: enclosure + textures + previews
    (tree["enclosure"] / "enclosure.stl").write_text("; placeholder STL\n")
    _write_placeholder_png(tree["textures"] / "texture.png", "texture.png")
    _write_placeholder_png(tree["textures"] / "heightmap.png", "heightmap.png")
    _write_placeholder_png(tree["previews"] / "hero.png", "hero.png")
    _write_placeholder_png(tree["previews"] / "iso.png", "iso.png")
    _write_placeholder_png(tree["previews"] / "top.png", "top.png")
    _write_placeholder_png(tree["previews"] / "side.png", "side.png")

    previews = {
        "job": _public_url(sf, job_id, "job.json"),
        "stl": _public_url(sf, job_id, "enclosure/enclosure.stl"),
        "texture": _public_url(sf, job_id, "textures/texture.png"),
        "heightmap": _public_url(sf, job_id, "textures/heightmap.png"),
        "hero": _public_url(sf, job_id, "previews/hero.png"),
    }

    return CreateJobResponse(job_id=job_id, subfolder=sf, status="created", public=previews)

@router.get("/jobs/{job_id}")
def get_job(job_id: str, subfolder: str | None = None):
    ensure_dirs()
    sf = sanitize_subfolder(subfolder)
    root = job_root(SURFACE_OUTPUT_DIR, job_id, sf)
    job_file = root / "job.json"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="job not found")
    return json.loads(job_file.read_text())
