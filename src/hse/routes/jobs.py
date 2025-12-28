from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from hse.contracts.envelopes import job_status, now_iso
from hse.fs.paths import job_dir, manifest_path, public_root, sanitize_subfolder
from hse.fs.writer import write_manifest, write_surface_job_json
from fastapi.responses import JSONResponse
from hexforge_contracts import load_schema, validate_json



router = APIRouter(tags=["surface"])


def _nonempty(p):
    return p.exists() and p.is_file() and p.stat().st_size > 0


def infer_status_from_files(job_id: str, *, subfolder: Optional[str] = None) -> str:
    root = job_dir(job_id, subfolder=subfolder)

    hero = root / "previews" / "hero.png"
    stl  = root / "enclosure" / "enclosure.stl"
    tex  = root / "textures" / "texture.png"
    hmap = root / "textures" / "heightmap.png"

    # ✅ COMPLETE only when required outputs exist AND are non-empty
    if (
        _nonempty(hero)
        and _nonempty(stl)
        and _nonempty(tex)
        and _nonempty(hmap)
    ):
        return "complete"

    # 🔄 RUNNING once work has visibly started
    if (
        (root / "textures").exists()
        or (root / "enclosure").exists()
        or (root / "job.json").exists()
    ):
        return "running"

    # ⏳ Otherwise still queued
    return "queued"


@router.post("/jobs")
async def create_job(req: Request) -> Dict[str, Any]:
    """
    Surface v1 contract:
      POST returns job_status envelope:
        { job_id, status, service, updated_at, (optional result/...) }

    Also writes:
      - job.json (public-facing Surface v1 job doc)    [queued]
      - job_manifest.json (contract-valid manifest)    [no status inside]
    """
    body = await req.json()

    job_id = secrets.token_hex(8)
    subfolder = sanitize_subfolder(body.get("subfolder", None))
    created_at = now_iso()

    # Write Surface v1 job.json immediately (public doc exists from creation)
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        params=body or {},
        artifacts={},
    )

    # Write contract-valid manifest immediately
    # IMPORTANT: do NOT pass public={} (schema requires full public object)
    write_manifest(
        job_id=job_id,
        subfolder=subfolder,
        updated_at=created_at,
        # public=None -> writer builds the default contract-shaped public object
    )

    pub_root = public_root(job_id, subfolder=subfolder)

    return job_status(
        job_id=job_id,
        status="queued",
        service="hexforge-glyphengine",
        updated_at=created_at,
        result={
            "public_root": pub_root,
            "job_manifest": f"{pub_root}/job_manifest.json",
            "job_json": f"{pub_root}/job.json",
        },
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, subfolder: Optional[str] = None) -> Dict[str, Any]:
    """
    Surface v1 contract:
      GET returns job_status envelope.

    Deterministic lookup requires the correct subfolder if the job was created
    under one: /assets/surface/<subfolder>/<job_id>/...
    """
    subfolder = sanitize_subfolder(subfolder)

    root = job_dir(job_id, subfolder=subfolder)
    if not root.exists():
        raise HTTPException(status_code=404, detail="job not found")

    mpath = manifest_path(job_id, subfolder=subfolder)
    pub_root = public_root(job_id, subfolder=subfolder)

    # Prefer manifest (for updated_at + authoritative public_root)
    if mpath.exists():
        doc = json.loads(mpath.read_text(encoding="utf-8"))
        updated_at = doc.get("updated_at") or now_iso()
        pub_root = doc.get("public_root") or pub_root

        status = infer_status_from_files(job_id, subfolder=subfolder)

        return job_status(
            job_id=job_id,
            status=status,
            service="hexforge-glyphengine",
            updated_at=updated_at,
            result={
                "public_root": pub_root,
                "job_manifest": f"{pub_root}/job_manifest.json",
                "job_json": f"{pub_root}/job.json",
            },
        )

    # Fallback if manifest missing
    status = infer_status_from_files(job_id, subfolder=subfolder)
    return job_status(
        job_id=job_id,
        status=status,
        service="hexforge-glyphengine",
        updated_at=now_iso(),
        result={
            "public_root": pub_root,
            "job_manifest": f"{pub_root}/job_manifest.json",
            "job_json": f"{pub_root}/job.json",
        },
    )


@router.get("/jobs/{job_id}/manifest")
async def get_manifest(job_id: str, subfolder: Optional[str] = None) -> JSONResponse:
    subfolder = sanitize_subfolder(subfolder)

    root = job_dir(job_id, subfolder=subfolder)
    if not root.exists():
        raise HTTPException(status_code=404, detail="job not found")

    mpath = manifest_path(job_id, subfolder=subfolder)
    if not mpath.exists():
        raise HTTPException(status_code=404, detail="job_manifest.json not found")

    doc = json.loads(mpath.read_text(encoding="utf-8"))

    schema = load_schema("job_manifest.schema.json")
    validate_json(doc, schema)

    return JSONResponse(content=doc)
