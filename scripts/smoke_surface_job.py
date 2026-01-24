#!/usr/bin/env python3
"""
Run Surface jobs end-to-end locally and assert outputs exist.

Usage:
    python scripts/smoke_surface_job.py                        # legacy tile
    python scripts/smoke_surface_job.py --target pi4b_case --emboss-mode lid
    python scripts/smoke_surface_job.py --all                  # tile + pi4b variants
"""
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hse.contracts.envelopes import now_iso
from hse.fs.paths import job_dir, manifest_path
from hse.fs.writer import write_surface_job_json
from hse.routes.jobs import infer_status_from_files
from hse.workers.surface_worker import run_surface_job
from hse.utils.geometry import parse_stl_metadata
from PIL import ImageStat, Image, ImageDraw


def assert_exists(root: Path, rel: str) -> Path:
    fp = root / rel
    if not fp.is_file() or fp.stat().st_size == 0:
        raise AssertionError(f"missing or empty output: {rel}")
    return fp


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_fixture_heightmap(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("L", (128, 128), 0)
    draw = ImageDraw.Draw(img)
    for y in range(128):
        val = int(40 + (y / 127) * 180)
        draw.line((0, y, 127, y), fill=val)
    draw.rectangle((32, 32, 96, 96), outline=220, width=2)
    img.save(path)
    return path


def _expected_required(target: str, emboss_mode: Optional[str]) -> Tuple[List[str], bool]:
    req = [
        "inputs/input_heightmap.png",
        "textures/heightmap.png",
        "textures/texture.png",
        "previews/hero.png",
    ]
    if target in {"pi4b_case", "board_case"}:
        req.extend(["pi4b_case_base.stl", "pi4b_case_lid.stl"])
        panel_needed = (emboss_mode or "lid").lower() in {"panel", "both"}
        if panel_needed:
            req.append("pi4b_case_panel.stl")
        return req, panel_needed
    req.append("enclosure/enclosure.stl")
    return req, False


def run_scenario(job_id: str, target: str, emboss_mode: Optional[str], *, board: Optional[str] = None) -> None:
    subfolder = os.getenv("SUBFOLDER") or None
    root = job_dir(job_id, subfolder=subfolder)
    fixture = _make_fixture_heightmap(Path(".tmp/fixtures/heightmap.png"))
    fixture_hash = _sha256_file(fixture)
    heightmap_url = fixture.resolve().as_uri()

    params: Dict[str, object] = {"heightmap_url": heightmap_url, "target": target}
    if board:
        params["board"] = board
    if emboss_mode:
        params["emboss_mode"] = emboss_mode

    created_at = now_iso()
    write_surface_job_json(
        job_id=job_id,
        subfolder=subfolder,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        params=params,
        artifacts=None,
    )

    run_surface_job(job_id, subfolder=subfolder)

    man_path = manifest_path(job_id, subfolder=subfolder)
    assert man_path.is_file(), "manifest not written"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    public_root = manifest.get("public_root") or ""

    public = manifest.get("public") or {}
    if target in {"pi4b_case", "board_case"}:
        board_case_pub = public.get("board_case") or {}
        for k in ["base", "lid"]:
            val = board_case_pub.get(k)
            if not val or not str(val).startswith(public_root):
                raise AssertionError(f"public.board_case.{k} missing or wrong root: {val}")
        if emboss_mode in {"panel", "both"}:
            val = board_case_pub.get("panel")
            if not val or not str(val).startswith(public_root):
                raise AssertionError(f"public.board_case.panel missing or wrong root: {val}")
        if target == "pi4b_case":
            pi4b_pub = public.get("pi4b_case") or {}
            for k in ["base", "lid"]:
                if not pi4b_pub.get(k):
                    raise AssertionError(f"public.pi4b_case.{k} missing")

    req, panel_needed = _expected_required(target, emboss_mode)
    for rel in req:
        assert_exists(root, rel)

    if target in {"pi4b_case", "board_case"}:
        panel_path = root / "pi4b_case_panel.stl"
        if panel_needed:
            assert_exists(root, "pi4b_case_panel.stl")
        else:
            if panel_path.exists():
                raise AssertionError("panel output should not exist for emboss_mode=lid")

    inp = root / "inputs" / "input_heightmap.png"
    hmap = root / "textures" / "heightmap.png"
    if _sha256_file(inp) != fixture_hash:
        raise AssertionError("input_heightmap hash mismatch")
    if _sha256_file(hmap) != fixture_hash:
        raise AssertionError("texture heightmap hash mismatch")

    hero_img = Image.open(root / "previews" / "hero.png").convert("RGB")
    var = ImageStat.Stat(hero_img).var
    if sum(var) < 10:
        raise AssertionError(f"hero preview variance too low: {var}")

    geo = manifest.get("geometry_check") or {}
    if not geo.get("passed"):
        raise AssertionError(f"geometry check failed: {geo}")
    if geo.get("z_range_mm", 0) < 0.2:
        raise AssertionError(f"z_range too small: {geo}")

    outs = {o["path"]: o for o in manifest.get("outputs", [])}
    meta_inp = outs.get("inputs/input_heightmap.png") or {}
    if meta_inp.get("checksum") != fixture_hash:
        raise AssertionError(f"manifest checksum mismatch for input: {meta_inp}")
    if meta_inp.get("source_url") != heightmap_url:
        raise AssertionError(f"manifest source_url mismatch: {meta_inp}")
    if meta_inp.get("width") != 128 or meta_inp.get("height") != 128:
        raise AssertionError(f"manifest dims mismatch: {meta_inp}")

    public_root = manifest.get("public_root") or ""
    if not public_root.startswith("/assets/surface"):
        raise AssertionError(f"unexpected public_root: {public_root}")

    for rel, entry in outs.items():
        if entry.get("exists"):
            fs_path = root / rel
            if not fs_path.exists():
                raise AssertionError(f"manifest lists missing file: {rel}")
            if fs_path.stat().st_size == 0:
                raise AssertionError(f"manifest lists empty file: {rel}")
        if entry.get("public_url") and not entry["public_url"].startswith(f"{public_root.rstrip('/')}/"):
            raise AssertionError(f"public_url mismatch for {rel}: {entry['public_url']} (root {public_root})")

    if target in {"pi4b_case", "board_case"}:
        for key in ["pi4b_case_base.stl", "pi4b_case_lid.stl"]:
            entry = outs.get(key)
            if not entry or not entry.get("exists"):
                raise AssertionError(f"manifest missing or marked absent: {key}")
        panel_entry = outs.get("pi4b_case_panel.stl")
        if panel_needed and (not panel_entry or not panel_entry.get("exists")):
            raise AssertionError("manifest missing panel entry for panel emboss")
        if not panel_needed and panel_entry and panel_entry.get("exists"):
            raise AssertionError("manifest should not report panel output for emboss_mode=lid")

    # Geometry sanity: embossed parts must have non-zero z range
    if target in {"pi4b_case", "board_case"}:
        lid_meta = parse_stl_metadata(root / "pi4b_case_lid.stl")
        if lid_meta.z_range_mm <= 0.05:
            raise AssertionError(f"lid z_range too small: {lid_meta.z_range_mm}")
        if panel_needed:
            panel_meta = parse_stl_metadata(root / "pi4b_case_panel.stl")
            if panel_meta.z_range_mm <= 0.05:
                raise AssertionError(f"panel z_range too small: {panel_meta.z_range_mm}")
    else:
        tile_meta = parse_stl_metadata(root / "enclosure/enclosure.stl")
        if tile_meta.z_range_mm <= 0.05:
            raise AssertionError(f"tile z_range too small: {tile_meta.z_range_mm}")

    status = infer_status_from_files(job_id, subfolder=subfolder)
    if status != "complete":
        raise AssertionError(f"job status not complete: {status}")

    expected_root = Path(os.getenv("SURFACE_OUTPUT_DIR", "/data/hexforge3d/surface")).resolve()
    if expected_root.name != "surface":
        expected_root = expected_root / "surface"
    if subfolder:
        expected_root = expected_root / subfolder
    expected_root = expected_root / job_id
    if root.resolve() != expected_root:
        raise AssertionError(f"job root mismatch: {root} != {expected_root}")

    print(f"[smoke] ✅ {target} job {job_id} complete at {root} (emboss_mode={emboss_mode or 'default'}, board={board or 'n/a'})")
    print(f"[smoke] manifest: {man_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Surface smoke tests")
    parser.add_argument("job_id", nargs="?", default=None, help="Optional job id override")
    parser.add_argument("--target", choices=["tile", "pi4b_case", "board_case"], default=None)
    parser.add_argument("--emboss-mode", dest="emboss_mode", default=None, help="lid|panel|both for pi4b_case")
    parser.add_argument("--board", dest="board", default=None, help="Board id for board_case")
    parser.add_argument("--tile", action="store_true", help="Run only legacy tile scenario")
    parser.add_argument("--pi4b", action="store_true", help="Run pi4b_case scenarios (lid, panel, both)")
    parser.add_argument("--board-case", action="store_true", help="Run board_case scenarios (default board pi4b)")
    parser.add_argument("--all", action="store_true", help="Run tile + pi4b_case lid/panel/both")
    args = parser.parse_args()

    scenarios: List[Tuple[str, Optional[str], Optional[str]]] = []
    if args.tile:
        scenarios.append(("tile", None, None))
    if args.pi4b:
        scenarios.extend([
            ("pi4b_case", "lid", None),
            ("pi4b_case", "panel", None),
            ("pi4b_case", "both", None),
        ])
    if args.board_case:
        scenarios.append(("board_case", args.emboss_mode or "lid", args.board or "pi4b"))
    if args.all or (not scenarios and args.target is None):
        scenarios = [
            ("tile", None, None),
            ("pi4b_case", "lid", None),
            ("pi4b_case", "panel", None),
            ("pi4b_case", "both", None),
            ("board_case", "lid", args.board or "pi4b"),
        ]
    elif not scenarios:
        default_mode = "lid" if args.target == "pi4b_case" else None
        scenarios = [(args.target or "tile", args.emboss_mode or default_mode, args.board if (args.target or "tile") == "board_case" else None)]

    for target, emboss_mode, board in scenarios:
        jid = args.job_id or secrets.token_hex(6)
        run_scenario(jid, target, emboss_mode, board=board)
        args.job_id = None


if __name__ == "__main__":
    main()
