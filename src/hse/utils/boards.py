from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from hse.contracts import validate_contract

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_BOARD_ROOT = Path(os.getenv("HSE_BOARD_DEFS_ROOT", Path(__file__).resolve().parents[3] / "schemas" / "boards"))
_BOARD_PRESET_ROOT = _BOARD_ROOT / "presets"


def board_defs_root() -> Path:
    return _BOARD_ROOT


@lru_cache(maxsize=None)
def load_board_def(board_id: str) -> Dict[str, object]:
    bid = (board_id or "").strip().lower()
    if not _ID_RE.match(bid):
        raise ValueError(f"invalid board id: {board_id}")

    path = _BOARD_ROOT / f"{bid}.json"
    if not path.exists():
        raise FileNotFoundError(f"board definition not found: {bid}")

    data = json.loads(path.read_text(encoding="utf-8"))
    validate_contract(data, "board_def.schema.json")
    if data.get("id") != bid:
        raise ValueError(f"board id mismatch: expected {bid}, got {data.get('id')}")
    return data


def list_board_defs() -> List[str]:
    if not _BOARD_ROOT.exists():
        return []
    return sorted(path.stem for path in _BOARD_ROOT.glob("*.json") if path.is_file())


@lru_cache(maxsize=None)
def load_board_preset(name: str = "pi4b_case") -> Dict[str, object]:
    preset_id = (name or "pi4b_case").strip().lower() or "pi4b_case"
    path = _BOARD_PRESET_ROOT / f"{preset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"board preset not found: {preset_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def default_board_case_id() -> str:
    try:
        preset = load_board_preset("pi4b_case")
        bid = str(preset.get("board") or "pi4b").strip().lower()
        return bid or "pi4b"
    except Exception:
        return "pi4b"


__all__ = ["load_board_def", "list_board_defs", "board_defs_root"]
