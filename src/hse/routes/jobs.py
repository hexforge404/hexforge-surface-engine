# src/hse/routes/jobs.py
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from hse.contracts.envelopes import job_status, now_iso
from hse.fs.paths import assets_root, job_dir, manifest_path, job_json_path
from hse.fs.writer import write_manifest

router = APIRouter(tags=["surface"])


def infer_status_from_files(job_id: str) -> str:
    """
    Minimal inference until a worker explicitly updates status:
      - complete if previews/hero.png exists
      - running if job.json exists
      - queued otherwise
    """
    root = job_dir(job_id)
    if (root / "previews" / "hero.png").exists():
        return "complete"
    if (root / "job.json").exists():
        return "running"
    return "queued"


@router.post("/jobs")
async def create_job(req: Request):
    """
    Surface v1 contract:
      POST returns job_status envelope:
        { job_id, status, service, updated_at, result:{ public:"/assets/..." } }

    Also writes an initial job_manifest.json (status=queued).
    """
    body = await req.json()

    # If you already generate job IDs elsewhere, replace this with your existing call.
    job_id = secrets.token_hex(8)
    subfolder = body.get("subfolder", None)

    created_at = now_iso()

    # Write initial manifest immediately (authoritative record exists from creation)
    write_manifest(
        job_id=job_id,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        subfolder=subfolder,
        public={},
    )

    return job_status(
        job_id=job_id,
        status="queued",
        public_root=assets_root(job_id, subfolder=subfolder),
        updated_at=created_at,
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """
    Surface v1 contract:
      GET returns job_status envelope.

    Prefers job_manifest.json if present; otherwise infers state from files.
    """
    root = job_dir(job_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="job not found")

    mpath = manifest_path(job_id)

    if mpath.exists():
        doc = json.loads(mpath.read_text(encoding="utf-8"))
        status = doc.get("status") or infer_status_from_files(job_id)
        updated_at = doc.get("updated_at") or now_iso()
        public_root = doc.get("public_root") or assets_root(job_id)
        return job_status(
            job_id=job_id,
            status=status,
            public_root=public_root,
            updated_at=updated_at,
        )

    # Fallback if manifest is missing for some reason
    status = infer_status_from_files(job_id)
    return job_status(
        job_id=job_id,
        status=status,
        public_root=assets_root(job_id),
        updated_at=now_iso(),
    )
