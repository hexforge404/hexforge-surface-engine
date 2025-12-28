from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_status(
    *,
    job_id: str,
    status: str,
    service: str,
    updated_at: Optional[str] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Contract-valid job_status envelope.
    Must match job_status.schema.json exactly (additionalProperties: false).
    """
    payload: Dict[str, Any] = {
        "job_id": job_id,
        "status": status,          # queued | running | complete | failed
        "service": service,
        "updated_at": updated_at or now_iso(),
    }

    if progress is not None:
        payload["progress"] = progress
    if message is not None:
        payload["message"] = message
    if error is not None:
        payload["error"] = error
    if result is not None:
        payload["result"] = result

    return payload


def job_manifest_v1(
    *,
    job_id: str,
    service: str,
    public_root: str,
    public: Dict[str, Any],
    subfolder: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    job_manifest.schema.json-compatible structure (v1).
    Must match schema exactly (additionalProperties: false).
    """
    return {
        "version": "v1",
        "job_id": job_id,
        "service": service,
        "updated_at": updated_at or now_iso(),
        "subfolder": subfolder,
        "public_root": public_root,
        "public": public,
    }


__all__ = ["now_iso", "job_status", "job_manifest_v1"]
