from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from hse.contracts.envelopes import job_manifest_v1, now_iso
from hse.fs.paths import job_dir, manifest_path, public_root
from hexforge_contracts import load_schema, validate_json


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def write_manifest(
    *,
    job_id: str,
    subfolder: Optional[str],
    status: str,
    created_at: str,
    updated_at: Optional[str] = None,
    public: Optional[Dict[str, str]] = None,
) -> Path:
    updated_at = updated_at or now_iso()
    doc = job_manifest_v1(
        job_id=job_id,
        subfolder=subfolder,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        public_root=public_root(job_id, subfolder=subfolder),
        public=public or {},
    )
    p = manifest_path(job_id)
    schema = load_schema("job_manifest.schema.json")
    validate_json(doc, schema)
    write_json_atomic(p, doc)
    return p
