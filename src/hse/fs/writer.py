from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from hse.contracts.envelopes import job_manifest_v1, now_iso
from hse.fs.paths import job_json_path, manifest_path, public_root, sanitize_subfolder

from hexforge_contracts import load_schema, validate_json


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _default_public_manifest(public_base: str) -> Dict[str, Any]:
    """
    Build a contract-shaped `public` object for job_manifest.schema.json.

    IMPORTANT:
    - All values must be URLs that begin with /assets/
    - The shape must include:
        job_json
        enclosure: { stl, (optional obj/glb) }
        textures: { texture_png, heightmap_png, (optional heightmap_exr) }
        previews: { hero, iso, top, side }
    """
    # Normalize just in case (avoid trailing slash duplicates)
    base = public_base.rstrip("/")

    return {
        "job_json": f"{base}/job.json",
        "enclosure": {
            "stl": f"{base}/enclosure/enclosure.stl",
            # "obj": f"{base}/enclosure/enclosure.obj",
            # "glb": f"{base}/enclosure/enclosure.glb",
        },
        "textures": {
            "texture_png": f"{base}/textures/texture.png",
            "heightmap_png": f"{base}/textures/heightmap.png",
            # "heightmap_exr": f"{base}/textures/heightmap.exr",
        },
        "previews": {
            "hero": f"{base}/previews/hero.png",
            "iso": f"{base}/previews/iso.png",
            "top": f"{base}/previews/top.png",
            "side": f"{base}/previews/side.png",
        },
    }


def write_manifest(
    *,
    job_id: str,
    subfolder: Optional[str],
    # Back-compat params (older callers may still send these).
    # The contract schema does NOT allow them in job_manifest.json.
    status: Optional[str] = None,      # ignored (schema forbids)
    created_at: Optional[str] = None,  # ignored (schema forbids)
    # Current contract fields:
    service: str = "hexforge-glyphengine",
    updated_at: Optional[str] = None,
    public: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Writes job_manifest.json (contract-valid manifest).
    Validated against hexforge-contracts job_manifest.schema.json.

    NOTE:
    - We intentionally ignore `status` and `created_at` for this file because
      job_manifest.schema.json uses additionalProperties:false and does not
      include those fields. Status belongs in job.json (service-specific doc).
    """
    _ = status
    _ = created_at

    subfolder = sanitize_subfolder(subfolder)
    updated_at = updated_at or now_iso()

    pub_root = public_root(job_id, subfolder=subfolder)

    # Contract requires /assets/ prefix (schema enforces ^/assets/)
    if not pub_root.startswith("/assets/"):
        raise ValueError(
            f"public_root() must return a /assets/... path for contract compliance. Got: {pub_root}"
        )

    doc = job_manifest_v1(
        job_id=job_id,
        service=service,
        subfolder=subfolder,
        updated_at=updated_at,
        public_root=pub_root,
        public=public or _default_public_manifest(pub_root),
    )

    p = manifest_path(job_id, subfolder=subfolder)

    schema = load_schema("job_manifest.schema.json")
    validate_json(doc, schema)

    write_json_atomic(p, doc)
    return p


def write_surface_job_json(
    *,
    job_id: str,
    subfolder: Optional[str],
    status: str,
    created_at: str,
    updated_at: Optional[str],
    params: Dict[str, Any],
    artifacts: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Writes job.json (Surface v1 job document).

    NOTE: This intentionally keeps URLs relative and uses the canonical
    /assets/surface/<subfolder?>/<job_id> base.
    """
    subfolder = sanitize_subfolder(subfolder)
    updated_at = updated_at or now_iso()

    doc = {
        "job_id": job_id,
        "service": "hexforge-glyphengine",
        "version": "v1",
        "status": status,  # queued | running | complete | failed
        "created_at": created_at,
        "updated_at": updated_at,
        "public_base_url": public_root(job_id, subfolder=subfolder),
        "output_dir": str(job_json_path(job_id, subfolder=subfolder).parent),
        "params": params,
        "artifacts": artifacts or {},
    }

    p = job_json_path(job_id, subfolder=subfolder)

    # Optional strict validation later (if/when surface_job.schema.json is in contracts)
    # schema = load_schema("surface_job.schema.json")
    # validate_json(doc, schema)

    write_json_atomic(p, doc)
    return p
