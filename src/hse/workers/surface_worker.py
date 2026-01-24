import hashlib
import json
import math
import os
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh

from hse.contracts.envelopes import now_iso
from hse.fs.paths import assert_valid_job_id, job_dir, job_json_path, public_root, sanitize_subfolder
from hse.fs.writer import build_outputs, write_manifest, write_surface_job_json
from hse.utils.geometry import evaluate_geometry, parse_stl_metadata, sample_heightmap_range
from hse.utils.render import render_hero_from_stl
from hse.utils.boards import default_board_case_id, load_board_def
from PIL import Image, ImageOps


MIN_DISPLACEMENT_MM = float(os.getenv("GLYPHENGINE_MIN_DISPLACEMENT_MM", "0.2"))
NON_UNIFORM_THRESHOLD = float(os.getenv("GLYPHENGINE_NONUNIFORM_HEIGHTMAP", "1.0"))
DISPLACEMENT_SCALE_MM = float(os.getenv("GLYPHENGINE_DISPLACEMENT_SCALE_MM", "2.5"))
DEBUG = os.getenv("GLYPHENGINE_DEBUG", "0") not in {"", "0", "false", "False", "FALSE", None}


def _debug(msg: str, **kwargs: object) -> None:
    if not DEBUG:
        return
    extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[worker-debug] {msg} {extras}")


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
        bid = (value or "").strip().lower()
    except Exception:
        bid = ""
    if not bid:
        return default_board_case_id()
    return bid


def _read_job_state(job_id: str, subfolder: Optional[str]) -> Tuple[str, Dict, Dict]:
    """Preserve created_at and params/artifacts from the queued job.json."""
    p = job_json_path(job_id, subfolder=subfolder)
    if p.exists():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                created = str(doc.get("created_at") or now_iso())
                params = doc.get("params") or {}
                artifacts = doc.get("artifacts") or {}
                return created, params, artifacts
        except Exception:
            pass
    return now_iso(), {}, {}


def _write_colorized_heightmap(heightmap: Path, preview_path: Path, texture_path: Path) -> None:
    img = Image.open(heightmap).convert("L")
    colored = ImageOps.colorize(img, black="#162032", white="#8fd3ff")
    colored.save(preview_path)
    colored.save(texture_path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_heightmap(url: str, dest_inputs: Path, dest_texture: Path) -> Dict[str, object]:
    if not url:
        raise RuntimeError("missing heightmap_url")

    dest_inputs.parent.mkdir(parents=True, exist_ok=True)
    dest_texture.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    if not data:
        raise RuntimeError("empty heightmap download")

    dest_inputs.write_bytes(data)
    dest_texture.write_bytes(data)

    img = Image.open(dest_inputs).convert("L")
    width, height = img.size
    checksum = _sha256_file(dest_inputs)

    return {
        "checksum": checksum,
        "width": width,
        "height": height,
        "source_url": url,
    }


def _compute_normal(a: Tuple[float, float, float], b: Tuple[float, float, float], c: Tuple[float, float, float]) -> Tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def _write_relief_stl(heightmap: Path, stl_path: Path, *, scale_mm: float = DISPLACEMENT_SCALE_MM) -> None:
    img = Image.open(heightmap).convert("L").resize((64, 64))
    pixels = list(img.getdata())
    w, h = img.size
    heights: List[List[float]] = []
    for y in range(h):
        row = []
        for x in range(w):
            val = pixels[y * w + x] / 255.0
            row.append(val * scale_mm)
        heights.append(row)

    stl_path.parent.mkdir(parents=True, exist_ok=True)
    with stl_path.open("w", encoding="ascii") as fh:
        fh.write("solid relief\n")
        pitch = 1.0
        for y in range(h - 1):
            for x in range(w - 1):
                p00 = (x * pitch, y * pitch, heights[y][x])
                p10 = ((x + 1) * pitch, y * pitch, heights[y][x + 1])
                p01 = (x * pitch, (y + 1) * pitch, heights[y + 1][x])
                p11 = ((x + 1) * pitch, (y + 1) * pitch, heights[y + 1][x + 1])

                for tri in ((p00, p10, p11), (p00, p11, p01)):
                    n = _compute_normal(*tri)
                    fh.write(f"  facet normal {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
                    fh.write("    outer loop\n")
                    for vx, vy, vz in tri:
                        fh.write(f"      vertex {vx:.6f} {vy:.6f} {vz:.6f}\n")
                    fh.write("    endloop\n  endfacet\n")
        fh.write("endsolid relief\n")


def _ensure_mesh_nonflat(path: Path, *, epsilon: float = 0.05, label: str = "mesh") -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"{label}_missing_or_empty: {path}")
    meta = parse_stl_metadata(path)
    if meta.z_range_mm <= epsilon:
        raise RuntimeError(f"{label}_flat: z_range_mm={meta.z_range_mm:.4f}")


def _box_mesh(extents: Tuple[float, float, float], center: Tuple[float, float, float]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    return mesh


def _heightmap_mesh(
    heightmap: Path,
    size_x: float,
    size_y: float,
    *,
    scale_mm: float,
    base: float,
    axis: str = "z",
) -> trimesh.Trimesh:
    """Create a simple displaced mesh from the heightmap on either the Z or Y axis."""
    img = Image.open(heightmap).convert("L").resize((80, 80))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    h, w = arr.shape
    step_x = size_x / max(w - 1, 1)
    step_y = size_y / max(h - 1, 1)

    vertices: List[Tuple[float, float, float]] = []
    for j in range(h):
        for i in range(w):
            x = -size_x / 2.0 + i * step_x
            span = -size_y / 2.0 + j * step_y
            delta = float(arr[j, i] * scale_mm)
            if axis == "y":
                vertices.append((x, base + delta, span))
            else:
                vertices.append((x, span, base + delta))

    faces: List[Tuple[int, int, int]] = []
    for j in range(h - 1):
        for i in range(w - 1):
            idx = j * w + i
            faces.append((idx, idx + 1, idx + w + 1))
            faces.append((idx, idx + w + 1, idx + w))

    return trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float32),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )


def _merge_meshes(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    usable = [m for m in meshes if m is not None and len(m.vertices) > 0]
    if not usable:
        raise RuntimeError("no meshes to merge")
    if len(usable) == 1:
        return usable[0]
    return trimesh.util.concatenate(usable)


def _generate_pi4b_case(heightmap: Path, root: Path, emboss_mode: str) -> Tuple[Dict[str, Optional[Path]], Path, Dict[str, Dict[str, object]]]:
    # Simple printable case with rails for a sliding panel
    outer_x, outer_y, base_height = 96.0, 66.0, 24.0
    wall_th = 2.2
    floor_th = 2.4
    lid_th = 2.6
    lid_gap = 0.4  # clearance between base and lid

    inner_x = outer_x - 2 * wall_th
    inner_y = outer_y - 2 * wall_th

    rail_len = inner_x - 6.0
    rail_width = 1.6
    rail_height = 12.0
    rail_base_z = floor_th + 3.0

    panel_th = 2.2
    panel_clearance = 0.35
    panel_width = rail_len - 6.0
    panel_height = rail_height - 2.0
    slot_width = panel_th + 2 * panel_clearance
    slot_half = slot_width / 2.0
    rail_y1 = -(slot_half + rail_width / 2.0)
    rail_y2 = slot_half + rail_width / 2.0
    end_stop = wall_th * 1.3
    end_stop_center_x = rail_len / 2.0 - end_stop / 2.0

    meshes_base = [
        _box_mesh((inner_x, inner_y, floor_th), (0.0, 0.0, floor_th / 2.0)),
        _box_mesh((outer_x, wall_th, base_height), (0.0, -(outer_y / 2.0 - wall_th / 2.0), base_height / 2.0)),
        _box_mesh((outer_x, wall_th, base_height), (0.0, outer_y / 2.0 - wall_th / 2.0, base_height / 2.0)),
        _box_mesh((wall_th, inner_y, base_height), (-(outer_x / 2.0 - wall_th / 2.0), 0.0, base_height / 2.0)),
        _box_mesh((wall_th, inner_y, base_height), ((outer_x / 2.0 - wall_th / 2.0), 0.0, base_height / 2.0)),
        _box_mesh((rail_len, rail_width, rail_height), (0.0, rail_y1, rail_base_z + rail_height / 2.0)),
        _box_mesh((rail_len, rail_width, rail_height), (0.0, rail_y2, rail_base_z + rail_height / 2.0)),
        _box_mesh((end_stop, slot_width, rail_height), (end_stop_center_x, 0.0, rail_base_z + rail_height / 2.0)),
    ]
    base_mesh = _merge_meshes(meshes_base)
    base_path = root / "pi4b_case_base.stl"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    base_mesh.export(base_path)

    lid_z0 = base_height + lid_gap
    lid_meshes = [
        _box_mesh((outer_x, outer_y, lid_th), (0.0, 0.0, lid_z0 + lid_th / 2.0)),
    ]
    if emboss_mode in {"lid", "both"}:
        relief = _heightmap_mesh(
            heightmap,
            size_x=outer_x - 6.0,
            size_y=outer_y - 6.0,
            scale_mm=DISPLACEMENT_SCALE_MM,
            base=lid_z0 + lid_th,
            axis="z",
        )
        lid_meshes.append(relief)
    lid_mesh = _merge_meshes(lid_meshes)
    lid_path = root / "pi4b_case_lid.stl"
    lid_mesh.export(lid_path)

    panel_path: Optional[Path] = None
    panel_mesh: Optional[trimesh.Trimesh] = None
    if emboss_mode in {"panel", "both"}:
        panel_center_x = -rail_len / 2.0 + 4.0  # leave room for the end stop
        panel_center_z = rail_base_z + panel_height / 2.0
        panel_mesh_parts = [
            _box_mesh((panel_width, panel_th, panel_height), (panel_center_x, 0.0, panel_center_z)),
        ]
        relief_panel = _heightmap_mesh(
            heightmap,
            size_x=panel_width - 4.0,
            size_y=panel_height - 2.0,
            scale_mm=DISPLACEMENT_SCALE_MM * 0.8,
            base=panel_th / 2.0,
            axis="y",
        )
        relief_panel.apply_translation((panel_center_x, panel_th / 2.0, panel_center_z))
        panel_mesh_parts.append(relief_panel)
        panel_mesh = _merge_meshes(panel_mesh_parts)
        panel_path = root / "pi4b_case_panel.stl"
        panel_mesh.export(panel_path)

    assembly_parts = [base_mesh, lid_mesh]
    if panel_mesh is not None:
        assembly_parts.append(panel_mesh)
    assembly_mesh = _merge_meshes(assembly_parts)
    assembly_path = root / "pi4b_case_assembly.stl"
    assembly_mesh.export(assembly_path)

    overrides: Dict[str, Dict[str, object]] = {
        "pi4b_case_base.stl": {"checksum": _sha256_file(base_path)},
        "pi4b_case_lid.stl": {"checksum": _sha256_file(lid_path)},
    }
    if panel_path:
        overrides["pi4b_case_panel.stl"] = {"checksum": _sha256_file(panel_path)}

    return {
        "base": base_path,
        "lid": lid_path,
        "panel": panel_path,
        "assembly": assembly_path,
    }, assembly_path, overrides


def _generate_board_case(heightmap: Path, root: Path, emboss_mode: str, board_id: str) -> Tuple[Dict[str, Optional[Path]], Path, Dict[str, Dict[str, object]]]:
    board_def = load_board_def(board_id)
    if board_def.get("id") in {"pi4b", "pi5"}:
        return _generate_pi4b_case(heightmap, root, emboss_mode)
    raise RuntimeError(f"board_case_unsupported:{board_def.get('id')}")


def run_surface_job(job_id: str, subfolder: Optional[str] = None) -> None:
    """
    Minimal worker loop:
    - preserves created_at
    - marks job running
    - simulates work
    - writes non-empty placeholder outputs
    - marks job complete
    - bumps manifest updated_at
    """
    job_id = assert_valid_job_id(job_id)
    subfolder = sanitize_subfolder(subfolder)
    root = job_dir(job_id, subfolder=subfolder)
    created_at, params, artifacts = _read_job_state(job_id, subfolder)
    target = _normalized_target((params or {}).get("target"))
    emboss_mode = _normalized_emboss_mode((params or {}).get("emboss_mode"), target=target)
    board_id = _normalized_board_id((params or {}).get("board")) if target == "board_case" else None
    artifacts = artifacts or None

    started_at = now_iso()
    pub_root = public_root(job_id, subfolder=subfolder)
    _debug("job_paths", assets_root=str(root.parent), job_root=str(root), pub_root=pub_root)

    # Mark running and publish draft manifest immediately
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="running",
        created_at=created_at,
        updated_at=started_at,
        started_at=started_at,
        params=params,
        artifacts=artifacts,
    )
    write_manifest(
        job_id=job_id,
        subfolder=subfolder,
        created_at=created_at,
        started_at=started_at,
        updated_at=started_at,
        target=target,
        emboss_mode=emboss_mode,
        board_id=board_id,
    )

    missing_outputs: List[str] = []
    geometry_result: Optional[Dict[str, object]] = None
    outputs_overrides: Dict[str, Dict[str, object]] = {}
    download_meta: Optional[Dict[str, object]] = None
    hero_stats: Optional[Dict[str, object]] = None
    failure_reason: str = "job_failed"

    try:
        (root / "textures").mkdir(parents=True, exist_ok=True)
        (root / "enclosure").mkdir(parents=True, exist_ok=True)
        (root / "previews").mkdir(parents=True, exist_ok=True)

        params_heightmap_url = (
            (params or {}).get("heightmap_url")
            or (params or {}).get("heightmap", {}).get("url")
            or (params or {}).get("heightmap_png")
            or (params or {}).get("texture", {}).get("heightmap_url")
        )
        if not params_heightmap_url:
            raise RuntimeError("missing heightmap_url in params")

        heightmap_path = root / "textures" / "heightmap.png"
        try:
            download_meta = _download_heightmap(
                params_heightmap_url,
                root / "inputs" / "input_heightmap.png",
                heightmap_path,
            )
        except Exception:
            failure_reason = "heightmap_download_failed"
            raise
        _debug("heightmap_downloaded", url=params_heightmap_url, bytes=heightmap_path.stat().st_size, path=str(heightmap_path))

        _write_colorized_heightmap(
            heightmap_path,
            root / "previews" / "iso.png",
            root / "textures" / "texture.png",
        )
        outputs_overrides["inputs/input_heightmap.png"] = {
            "checksum": download_meta.get("checksum"),
            "width": download_meta.get("width"),
            "height": download_meta.get("height"),
            "source_url": params_heightmap_url,
        }
        outputs_overrides["textures/heightmap.png"] = {
            "checksum": download_meta.get("checksum"),
            "width": download_meta.get("width"),
            "height": download_meta.get("height"),
        }

        generated_paths: Dict[str, Optional[Path]] = {}
        hero_input_stl: Path
        geometry_target: Path

        if target in {"pi4b_case", "board_case"}:
            generated_paths, assembly_path, case_overrides = _generate_board_case(heightmap_path, root, emboss_mode, board_id or "pi4b")
            try:
                base_path = generated_paths.get("base")
                lid_path = generated_paths.get("lid")
                panel_path = generated_paths.get("panel")
                if base_path is None or lid_path is None:
                    raise RuntimeError("board_case base or lid missing")
                _ensure_mesh_nonflat(base_path, label="base_stl")
                _ensure_mesh_nonflat(lid_path, label="lid_stl")
                if emboss_mode in {"panel", "both"}:
                    if panel_path is None:
                        raise RuntimeError("panel_missing")
                    _ensure_mesh_nonflat(panel_path, label="panel_stl")
                _ensure_mesh_nonflat(assembly_path, label="assembly_stl")
            except Exception:
                failure_reason = "board_case_mesh_invalid"
                raise

            hero_input_stl = assembly_path
            geometry_target = (generated_paths.get("lid") or generated_paths.get("base") or assembly_path)
            outputs_overrides.update(case_overrides)
            _debug(
                "board_case_generated",
                base=str(generated_paths.get("base")),
                lid=str(generated_paths.get("lid")),
                panel=str(generated_paths.get("panel")),
                assembly=str(assembly_path),
                board=board_id or "pi4b",
            )
        else:
            stl_path = root / "enclosure" / "enclosure.stl"
            generated_paths = {"stl": stl_path}
            _write_relief_stl(heightmap_path, stl_path, scale_mm=DISPLACEMENT_SCALE_MM)
            try:
                _ensure_mesh_nonflat(stl_path, label="enclosure_stl")
            except Exception:
                failure_reason = "enclosure_mesh_invalid"
                raise
            _debug("stl_written", path=str(stl_path), bytes=stl_path.stat().st_size)
            hero_input_stl = stl_path
            geometry_target = stl_path
            outputs_overrides["enclosure/enclosure.stl"] = {
                "checksum": _sha256_file(stl_path),
            }

        hero = root / "previews" / "hero.png"
        try:
            hero_stats = render_hero_from_stl(hero_input_stl, hero)
        except Exception:
            failure_reason = "hero_render_failed"
            raise
        outputs_overrides["previews/hero.png"] = {
            "checksum": _sha256_file(hero),
        }
        outputs_overrides["textures/texture.png"] = {
            "checksum": _sha256_file(root / "textures" / "texture.png"),
        }

        for name in ("iso", "top", "side"):
            preview_target = root / "previews" / f"{name}.png"
            preview_target.write_bytes(hero.read_bytes())

        required = {
            "previews/hero.png": hero,
            "previews/iso.png": root / "previews" / "iso.png",
            "previews/top.png": root / "previews" / "top.png",
            "previews/side.png": root / "previews" / "side.png",
            "textures/texture.png": root / "textures" / "texture.png",
            "textures/heightmap.png": heightmap_path,
            "inputs/input_heightmap.png": root / "inputs" / "input_heightmap.png",
        }
        if target in {"pi4b_case", "board_case"}:
            required["pi4b_case_base.stl"] = generated_paths.get("base") or (root / "pi4b_case_base.stl")
            required["pi4b_case_lid.stl"] = generated_paths.get("lid") or (root / "pi4b_case_lid.stl")
            if emboss_mode in {"panel", "both"}:
                required["pi4b_case_panel.stl"] = generated_paths.get("panel") or (root / "pi4b_case_panel.stl")
        else:
            required["enclosure/enclosure.stl"] = generated_paths["stl"]
        for rel_path, path in required.items():
            if not path.exists() or path.stat().st_size == 0:
                missing_outputs.append(rel_path)

        heightmap_range = sample_heightmap_range(heightmap_path)
        geometry_result = evaluate_geometry(
            stl_path=geometry_target,
            heightmap_range=heightmap_range,
            min_displacement_mm=MIN_DISPLACEMENT_MM,
            non_uniform_threshold=NON_UNIFORM_THRESHOLD,
        )

        if missing_outputs:
            raise RuntimeError(
                f"completed_without_outputs: missing {', '.join(sorted(missing_outputs))}"
            )

        if not geometry_result.get("passed", False):
            reason = geometry_result.get("reason") or "stl_geometry_check_failed"
            failure_reason = reason
            raise RuntimeError(f"{reason}: z_range_mm={geometry_result.get('z_range_mm')}")

        finished_at = now_iso()

        # Final status write AFTER assets and checks succeed
        write_manifest(
            job_id=job_id,
            subfolder=subfolder,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            updated_at=finished_at,
            geometry_check=geometry_result,
            outputs=build_outputs(root, pub_root, outputs_overrides, target=target, emboss_mode=emboss_mode),
            target=target,
            emboss_mode=emboss_mode,
            board_id=board_id,
        )

        write_surface_job_json(
            job_id=job_id,
            subfolder=subfolder,
            status="complete",
            created_at=created_at,
            updated_at=finished_at,
            started_at=started_at,
            finished_at=finished_at,
            params=params,
            artifacts=artifacts,
        )

        _debug(
            "job complete",
            job_id=job_id,
            stl=str(hero_input_stl),
            hero=str(hero),
            z_range=geometry_result.get("z_range_mm"),
        )

    except Exception as exc:
        finished_at = now_iso()
        reason = "completed_without_outputs" if missing_outputs else failure_reason
        if geometry_result and geometry_result.get("reason"):
            reason = str(geometry_result.get("reason"))

        error_payload: Dict[str, object] = {
            "message": str(exc),
            "code": reason,
            "detail": "surface job failed",
        }
        if missing_outputs:
            error_payload["missing"] = missing_outputs

        write_surface_job_json(
            job_id=job_id,
            subfolder=subfolder,
            status="failed",
            created_at=created_at,
            updated_at=finished_at,
            started_at=started_at,
            finished_at=finished_at,
            params=params,
            artifacts=artifacts,
            error=error_payload,
        )

        write_manifest(
            job_id=job_id,
            subfolder=subfolder,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            updated_at=finished_at,
            geometry_check=geometry_result,
            outputs=build_outputs(root, pub_root, outputs_overrides, target=target, emboss_mode=emboss_mode),
            target=target,
            emboss_mode=emboss_mode,
            board_id=board_id,
        )

        _debug("job failed", job_id=job_id, reason=reason, missing=missing_outputs)
        # Do not re-raise; the job json now reflects failure.
