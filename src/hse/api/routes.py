from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from hse.contracts.envelopes import job_status, now_iso
from hse.fs.paths import job_dir, public_root, manifest_path
from hse.fs.writer import write_manifest, write_json_atomic

router = APIRouter(prefix="/api/surface", tags=["surface"])


def infer_status(job_id: str) -> str:
    root = job_dir(job_id)
    # complete if hero exists
    if (root / "previews" / "hero.png").exists():
        return "complete"
    # running if any expected output folders exist
    if (root / "textures").exists() or (root / "enclosure").exists():
        return "running"
    # queued if manifest exists
    if manifest_path(job_id).exists():
        return "queued"
    return "queued"


@router.post("/jobs")
async def create_job(req: Request) -> Dict[str, Any]:
    """
    Contract:
      POST /api/surface/jobs -> job_status envelope
      required: job_id, status, service, updated_at
      optional: result.public
    Also writes job_manifest.json immediately.
    """
    body = await req.json()
    subfolder = body.get("subfolder", None)

    job_id = secrets.token_hex(8)
    created_at = now_iso()

    # Ensure job dir exists
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)

    # Snapshot request to job.json (keeps your legacy debugging behavior)
    write_json_atomic(d / "job.json", {"received_at": created_at, "request": body})

    # Write initial manifest (queued)
    write_manifest(
        job_id=job_id,
        subfolder=subfolder,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        public={},
    )

    return job_status(job_id=job_id, status="queued", public_root=public_root(job_id, subfolder=subfolder), updated_at=created_at)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    """
    Contract:
      GET /api/surface/jobs/{job_id} -> job_status envelope
    Prefers manifest; falls back to inferred status.
    """
    d = job_dir(job_id)
    if not d.exists():
        raise HTTPException(status_code=404, detail="job not found")

    mp = manifest_path(job_id)
    if mp.exists():
        doc = json.loads(mp.read_text(encoding="utf-8"))
        status = doc.get("status") or infer_status(job_id)
        updated_at = doc.get("updated_at") or now_iso()
        pr = doc.get("public_root") or public_root(job_id, subfolder=doc.get("subfolder"))
        return job_status(job_id=job_id, status=status, public_root=pr, updated_at=updated_at)

    # legacy fallback
    status = infer_status(job_id)
    return job_status(job_id=job_id, status=status, public_root=public_root(job_id), updated_at=now_iso())
