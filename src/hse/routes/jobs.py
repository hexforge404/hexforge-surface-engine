from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from hse.contracts.envelopes import job_status, now_iso
from hse.contracts import validate_contract
from hse.fs.paths import assert_valid_job_id, job_dir, manifest_path, public_root, sanitize_subfolder
from hse.fs.writer import write_manifest, write_surface_job_json
from hse.utils.boards import default_board_case_id
from fastapi.responses import JSONResponse



router = APIRouter(tags=["surface"])


def _nonempty(p):
    return p.exists() and p.is_file() and p.stat().st_size > 0


def _normalized_target(value):
    val = (value or "tile").strip().lower()
    if val == "board_case":
        return "board_case"
    if val == "pi4b_case":
        return "pi4b_case"
    return "tile"


def _normalized_emboss_mode(value, *, target: str):
    val = (value or "").strip().lower()
    if target in {"pi4b_case", "board_case"}:
        if val in {"panel", "lid", "both"}:
            return val
        return "lid"
    return "tile"


def _normalized_board_id(value):
    try:
        bid = (value or "").strip().lower()
    except Exception:
        bid = ""
    if not bid:
        return default_board_case_id()
    return bid


def infer_status_from_files(job_id: str, *, subfolder: Optional[str] = None) -> str:
    root = job_dir(job_id, subfolder=subfolder)

    hero = root / "previews" / "hero.png"
    stl  = root / "enclosure" / "enclosure.stl"
    tex  = root / "textures" / "texture.png"
    hmap = root / "textures" / "heightmap.png"
    job_json = root / "job.json"

    job_status_hint: Optional[str] = None
    params: Dict[str, Any] = {}
    if job_json.exists():
        try:
            doc = json.loads(job_json.read_text(encoding="utf-8"))
            job_status_hint = doc.get("status") if isinstance(doc, dict) else None
            params = doc.get("params") if isinstance(doc, dict) else {}
        except Exception:
            job_status_hint = None
            params = {}

    target = _normalized_target((params or {}).get("target"))
    emboss_mode = _normalized_emboss_mode((params or {}).get("emboss_mode"), target=target)

    # 🚫 Respect explicit failure recorded in job.json
    if job_status_hint == "failed":
        return "failed"

    # ✅ COMPLETE only when required outputs exist AND are non-empty
    required_files = [hero, tex, hmap]
    if target in {"pi4b_case", "board_case"}:
        required_files.append(root / "pi4b_case_base.stl")
        required_files.append(root / "pi4b_case_lid.stl")
        if emboss_mode in {"panel", "both"}:
            required_files.append(root / "pi4b_case_panel.stl")
    else:
        required_files.append(stl)

    if all(_nonempty(p) for p in required_files):
        return "complete"

    # If someone wrote "complete" prematurely, downgrade to failed to avoid
    # falsely advertising downloadable assets that do not exist yet.
    if job_status_hint == "complete":
        return "failed"

    # 🔄 RUNNING once work has visibly started
    if (
        (root / "textures").exists()
        or (root / "enclosure").exists()
        or job_status_hint == "running"
    ):
        return "running"

    # ⏳ Otherwise still queued (or defer to hint)
    if job_status_hint in {"queued", "failed"}:
        return job_status_hint
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
    target = _normalized_target(body.get("target"))
    emboss_mode = _normalized_emboss_mode(body.get("emboss_mode"), target=target)
    board_id = _normalized_board_id(body.get("board")) if target == "board_case" else None

    # Write Surface v1 job.json immediately (public doc exists from creation)
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        params=body or {},
        artifacts=None,
    )

    # Write contract-valid manifest immediately
    # IMPORTANT: do NOT pass public={} (schema requires full public object)
    write_manifest(
        job_id=job_id,
        subfolder=subfolder,
        updated_at=created_at,
        created_at=created_at,
        target=target,
        emboss_mode=emboss_mode,
        board_id=board_id,
        # public=None -> writer builds the default contract-shaped public object
    )

    pub_root = public_root(job_id, subfolder=subfolder)

    envelope = job_status(
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
    validate_contract(envelope, "job_status.schema.json")
    return envelope


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, subfolder: Optional[str] = None) -> Dict[str, Any]:
    """
    Surface v1 contract:
      GET returns job_status envelope.

    Deterministic lookup requires the correct subfolder if the job was created
    under one: /assets/surface/<subfolder>/<job_id>/...
    """
    try:
        job_id = assert_valid_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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

        envelope = job_status(
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
        validate_contract(envelope, "job_status.schema.json")
        return envelope

    # Fallback if manifest missing
    status = infer_status_from_files(job_id, subfolder=subfolder)
    envelope = job_status(
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
    validate_contract(envelope, "job_status.schema.json")
    return envelope


@router.get("/jobs/{job_id}/manifest")
async def get_manifest(job_id: str, subfolder: Optional[str] = None) -> JSONResponse:
    try:
        job_id = assert_valid_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    subfolder = sanitize_subfolder(subfolder)

    root = job_dir(job_id, subfolder=subfolder)
    if not root.exists():
        raise HTTPException(status_code=404, detail="job not found")

    mpath = manifest_path(job_id, subfolder=subfolder)
    if not mpath.exists():
        raise HTTPException(status_code=404, detail="job_manifest.json not found")

    doc = json.loads(mpath.read_text(encoding="utf-8"))

    validate_contract(doc, "job_manifest.schema.json")

    return JSONResponse(content=doc)
