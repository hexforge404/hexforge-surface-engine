from fastapi import APIRouter
from datetime import datetime
import secrets

from hse.models.job import CreateJobRequest, JobResponse
from hse.fs.paths import job_disk_root, public_paths, sanitize_subfolder
from hse.fs.writer import ensure_dirs, write_json

router = APIRouter(prefix="/api/surface", tags=["surface"])

@router.post("/jobs", response_model=JobResponse)
def create_job(req: CreateJobRequest):
    # Deterministic job_id (timestamp + token)
    job_id = f"hse_{datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')}_{secrets.token_hex(4)}"

    subfolder = sanitize_subfolder(req.subfolder)
    root = job_disk_root(job_id, subfolder)
    ensure_dirs(root)

    # Minimal job.json (enough for later rerender)
    write_json(root / "job.json", {
        "job_id": job_id,
        "status": "created",
        "subfolder": subfolder,
        "request": req.model_dump(),
    })

    # Minimal previews.json placeholder
    write_json(root / "previews.json", {
        "job_id": job_id,
        "status": "pending",
        "previews": {},
    })

    return JobResponse(
        job_id=job_id,
        status="created",
        result={"public": public_paths(job_id, subfolder)}
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, subfolder: str | None = None):
    subfolder_s = sanitize_subfolder(subfolder)
    # v1: return stable public paths even if files aren't generated yet
    return JobResponse(
        job_id=job_id,
        status="unknown",
        result={"public": public_paths(job_id, subfolder_s)}
    )
