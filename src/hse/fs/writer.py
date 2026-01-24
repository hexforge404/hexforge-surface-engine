from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hse.contracts import validate_contract
from hse.contracts.envelopes import job_manifest_v1, now_iso
from hse.fs.paths import job_dir, job_json_path, manifest_path, public_root, sanitize_subfolder
from hse.utils.boards import default_board_case_id, load_board_def


def _normalized_target(value: Optional[str]) -> str:
    val = (value or "tile").strip().lower()
    if val == "board_case":
        return "board_case"
    if val == "pi4b_case":
        return "pi4b_case"
    return "tile"


def _normalized_emboss_mode(value: Optional[str], *, target: str) -> str:
    val = (value or "").strip().lower()
    if target in {"pi4b_case", "board_case"}:
        if val in {"panel", "lid", "both"}:
            return val
        return "lid"
    return "tile"


def _normalized_board_id(value: Optional[str]) -> str:
    try:
        board_id = (value or "").strip().lower()
    except Exception:
        board_id = ""
    if not board_id:
        return default_board_case_id()
    return board_id


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _default_public_manifest(public_base: str, *, target: str = "tile", emboss_mode: str = "tile", board_id: Optional[str] = None) -> Dict[str, Any]:
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

    textures = {
        "texture_png": f"{base}/textures/texture.png",
        "heightmap_png": f"{base}/textures/heightmap.png",
    }

    previews = {
        "hero": f"{base}/previews/hero.png",
        "iso": f"{base}/previews/iso.png",
        "top": f"{base}/previews/top.png",
        "side": f"{base}/previews/side.png",
    }

    if target in {"pi4b_case", "board_case"}:
        case_paths: Dict[str, Any] = {
            "base": f"{base}/pi4b_case_base.stl",
            "lid": f"{base}/pi4b_case_lid.stl",
        }
        if emboss_mode in {"panel", "both"}:
            case_paths["panel"] = f"{base}/pi4b_case_panel.stl"

        public: Dict[str, Any] = {
            "job_json": f"{base}/job.json",
            "board_case": dict(case_paths),
            "textures": textures,
            "previews": previews,
        }

        if (board_id or "").lower() == "pi4b" or target == "pi4b_case":
            public["pi4b_case"] = dict(case_paths)

        return public

    return {
        "job_json": f"{base}/job.json",
        "enclosure": {
            "stl": f"{base}/enclosure/enclosure.stl",
        },
        "textures": textures,
        "previews": previews,
    }


def _default_artifacts(*, target: str = "tile", emboss_mode: str = "tile", board_id: Optional[str] = None, public_base: str) -> Dict[str, Any]:
    """Canonical public artifact URLs written by the worker."""
    base_url = public_base.rstrip("/")
    base = {
        "job_json": f"{base_url}/job.json",
        "previews": {
            "hero": f"{base_url}/previews/hero.png",
            "iso": f"{base_url}/previews/iso.png",
            "top": f"{base_url}/previews/top.png",
            "side": f"{base_url}/previews/side.png",
        },
        "textures": {
            "texture_png": f"{base_url}/textures/texture.png",
            "heightmap_png": f"{base_url}/textures/heightmap.png",
        },
    }

    if target in {"pi4b_case", "board_case"}:
        models: Dict[str, Any] = {
            "board_case_base": f"{base_url}/pi4b_case_base.stl",
            "board_case_lid": f"{base_url}/pi4b_case_lid.stl",
        }
        if emboss_mode in {"panel", "both"}:
            models["board_case_panel"] = f"{base_url}/pi4b_case_panel.stl"

        if target == "pi4b_case" or (board_id or "").lower() == "pi4b":
            models.update({
                "pi4b_case_base": f"{base_url}/pi4b_case_base.stl",
                "pi4b_case_lid": f"{base_url}/pi4b_case_lid.stl",
            })
            if emboss_mode in {"panel", "both"}:
                models["pi4b_case_panel"] = f"{base_url}/pi4b_case_panel.stl"
        base["models"] = models
        return base

    base["models"] = {"enclosure_stl": f"{base_url}/enclosure/enclosure.stl"}
    return base


# Stable mapping of expected outputs and their logical types.
_OUTPUT_SPEC_TILE: Tuple[Tuple[str, str], ...] = (
    ("inputs/input_heightmap.png", "input.heightmap"),
    ("job_manifest.json", "manifest"),
    ("job.json", "job_json"),
    ("previews/hero.png", "preview.hero"),
    ("previews/iso.png", "preview.iso"),
    ("previews/top.png", "preview.top"),
    ("previews/side.png", "preview.side"),
    ("enclosure/enclosure.stl", "mesh.stl"),
    ("textures/texture.png", "texture.diffuse"),
    ("textures/heightmap.png", "heightmap.png"),
)


def _output_spec_for_target(target: str, emboss_mode: str) -> Tuple[Tuple[str, str], ...]:
    if target in {"pi4b_case", "board_case"}:
        spec: List[Tuple[str, str]] = [
            ("inputs/input_heightmap.png", "input.heightmap"),
            ("job_manifest.json", "manifest"),
            ("job.json", "job_json"),
            ("previews/hero.png", "preview.hero"),
            ("previews/iso.png", "preview.iso"),
            ("previews/top.png", "preview.top"),
            ("previews/side.png", "preview.side"),
            ("pi4b_case_base.stl", "mesh.stl"),
            ("pi4b_case_lid.stl", "mesh.stl"),
            ("textures/texture.png", "texture.diffuse"),
            ("textures/heightmap.png", "heightmap.png"),
        ]
        if emboss_mode in {"panel", "both"}:
            spec.append(("pi4b_case_panel.stl", "mesh.stl"))
        return tuple(spec)
    return _OUTPUT_SPEC_TILE

def _output_entry(
    root: Path,
    rel_path: str,
    public_base: str,
    type_name: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fp = (root / rel_path).resolve()
    exists = fp.is_file()
    entry: Dict[str, Any] = {
        "path": rel_path,
        "type": type_name,
        "exists": bool(exists),
        "public_url": f"{public_base.rstrip('/')}/{rel_path}",
    }
    if exists:
        entry["size_bytes"] = fp.stat().st_size
    if overrides:
        entry.update({k: v for k, v in overrides.items() if v is not None})
    return entry


def build_outputs(
    job_root: Path,
    public_base: str,
    overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    target: str = "tile",
    emboss_mode: str = "tile",
) -> List[Dict[str, Any]]:
    """Build outputs list with optional per-path overrides (e.g., checksum, dimensions)."""
    job_root.mkdir(parents=True, exist_ok=True)
    spec = _output_spec_for_target(target, emboss_mode)
    return [
        _output_entry(job_root, rel_path, public_base, tname, (overrides or {}).get(rel_path))
        for rel_path, tname in spec
    ]


def write_manifest(
    *,
    job_id: str,
    subfolder: Optional[str],
    # Back-compat params (older callers may still send these).
    # The contract schema does NOT allow status; created_at is accepted.
    status: Optional[str] = None,      # ignored (schema forbids)
    created_at: Optional[str] = None,
    # Current contract fields:
    service: str = "hexforge-glyphengine",
    updated_at: Optional[str] = None,
    public: Optional[Dict[str, Any]] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    outputs: Optional[List[Dict[str, Any]]] = None,
    target: str = "tile",
    emboss_mode: str = "tile",
    board_id: Optional[str] = None,
    geometry_check: Optional[Dict[str, Any]] = None,
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

    job_root = job_dir(job_id, subfolder=subfolder)
    target = _normalized_target(target)
    emboss_mode = _normalized_emboss_mode(emboss_mode, target=target)
    board_id = _normalized_board_id(board_id)
    if target in {"board_case"}:
        load_board_def(board_id)

    if geometry_check is None:
        geometry_check = {
            "passed": False,
            "z_range_mm": 0,
            "triangles": 0,
            "bbox": {
                "min": [0, 0, 0],
                "max": [0, 0, 0],
            },
            "reason": "pending",
        }

    doc = job_manifest_v1(
        job_id=job_id,
        service=service,
        subfolder=subfolder,
        updated_at=updated_at,
        public_root=pub_root,
        public=public or _default_public_manifest(pub_root, target=target, emboss_mode=emboss_mode, board_id=board_id),
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        outputs=outputs if outputs is not None else build_outputs(job_root, pub_root, overrides=None, target=target, emboss_mode=emboss_mode),
        geometry_check=geometry_check,
    )

    p = manifest_path(job_id, subfolder=subfolder)

    validate_contract(doc, "job_manifest.schema.json")

    write_json_atomic(p, doc)
    return p


def write_surface_job_json(
    *,
    job_id: str,
    subfolder: Optional[str],
    status: str,
    created_at: str,
    updated_at: Optional[str],
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    params: Dict[str, Any],
    artifacts: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Writes job.json (Surface v1 job document).

    NOTE: This intentionally keeps URLs relative and uses the canonical
    /assets/surface/<subfolder?>/<job_id> base.
    """
    subfolder = sanitize_subfolder(subfolder)
    updated_at = updated_at or now_iso()

    target = _normalized_target((params or {}).get("target"))
    emboss_mode = _normalized_emboss_mode((params or {}).get("emboss_mode"), target=target)
    board_id = _normalized_board_id((params or {}).get("board")) if target in {"board_case"} else None
    if target == "board_case":
        load_board_def(board_id)

    doc = {
        "job_id": job_id,
        "service": "hexforge-glyphengine",
        "version": "v1",
        "status": status,  # queued | running | complete | failed
        "created_at": created_at,
        "updated_at": updated_at,
        "public_base_url": public_root(job_id, subfolder=subfolder),
        "output_dir": str(job_json_path(job_id, subfolder=subfolder).parent),
        "params": params or {},
        "artifacts": artifacts or _default_artifacts(target=target, emboss_mode=emboss_mode, board_id=board_id, public_base=public_root(job_id, subfolder=subfolder)),
        "error": error,
    }

    if started_at:
        doc["started_at"] = started_at
    if finished_at:
        doc["finished_at"] = finished_at

    p = job_json_path(job_id, subfolder=subfolder)

    validate_contract(doc, "job_json.schema.json")

    write_json_atomic(p, doc)
    return p


__all__ = [
    "write_json_atomic",
    "write_manifest",
    "write_surface_job_json",
    "build_outputs",
]
