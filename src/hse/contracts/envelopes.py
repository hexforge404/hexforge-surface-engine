from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_status(
    *,
    job_id: str,
    status: str,
    public_root: str,
    updated_at: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Minimal "job status envelope" used by the API.
    Keep this stable so other services can rely on it.
    """
    payload: Dict[str, Any] = {
        "job_id": job_id,
        "status": status,
        "public_root": public_root,
        "updated_at": updated_at or now_iso(),
    }
    if extra:
        payload.update(extra)
    return payload


def job_manifest_v1(
    *,
    job_id: str,
    service: str,
    public_root: str,
    public: Dict[str, Any],
    subfolder: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    status: str = "queued",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Minimal job_manifest.schema.json-compatible structure (v1).
    """
    doc: Dict[str, Any] = {
        "job_id": job_id,
        "service": service,
        "subfolder": subfolder,
        "public_root": public_root,
        "public": public,
        "status": status,
        "created_at": created_at or now_iso(),
        "updated_at": updated_at or now_iso(),
    }
    if extra:
        doc.update(extra)
    return doc


__all__ = ["now_iso", "job_status", "job_manifest_v1"]
