# Interfaces (Routes, Ports, Contracts)

This document defines the public and internal interface contract for the
**HexForge GlyphEngine** (formerly Surface Engine).

GlyphEngine provides the **Surface v1 API**, responsible for texture-driven
surface generation and enclosure geometry output.

All consumers (frontend, backend, assistant, future agents) MUST conform to
this contract.

---

## Service Identity

- Service name (Docker): **hexforge-glyphengine**
- Internal base URL: `http://hexforge-glyphengine:8092`
- Public API prefix (via nginx): `/api/surface/`
- Public asset prefix (via nginx): `/assets/surface/`

> ⚠️ Naming note  
> The service is called **GlyphEngine**, but the API and asset namespace
> intentionally remain **surface** to preserve backward compatibility.

---

## Ports

- **8092/tcp** — GlyphEngine HTTP API (Surface v1)
- **8188/tcp** — Optional local ComfyUI (internal only; not exposed)
- Blender integration runs headless; no public port required

---

## API Overview (Surface v1)

- All endpoints are versioned implicitly by repository version.
- All responses MUST include `job_id` and `status`.
- All public file references MUST be **relative paths** starting with `/assets/`.

---

## POST `/api/surface/jobs`

Creates a new surface + enclosure generation job.

### Request body (minimal v1 example)

```json
{
  "subfolder": "optional-project-or-product",
  "enclosure": {
    "inner_mm": [70, 40, 18],
    "wall_mm": 2.4,
    "lid_split": "z",
    "lid_ratio": 0.25,
    "features": {
      "standoffs": [],
      "cutouts": []
    }
  },
  "texture": {
    "prompt": "circuit board, cyberpunk, clean lines",
    "seed": 123,
    "size": [1024, 1024]
  }
}


GET /api/surface/jobs/{job_id}

Returns job status and public asset references once the job is complete or
fails.

GET /api/surface/jobs/{job_id}/assets

Returns a structured list of downloadable public assets associated with the job.

Response Contract (example)
{
  "job_id": "hse_2025-12-22_abcdef",
  "status": "complete",
  "result": {
    "public": {
      "root": "/assets/surface/<subfolder?>/<job_id>/",
      "enclosure": {
        "stl": "/assets/surface/.../enclosure/enclosure.stl",
        "handoff": "/assets/surface/.../enclosure/enclosure.obj"
      },
      "textures": {
        "texture_png": "/assets/surface/.../textures/texture.png",
        "heightmap_png": "/assets/surface/.../textures/heightmap.png",
        "heightmap_exr": "/assets/surface/.../textures/heightmap.exr"
      },
      "previews": {
        "hero": "/assets/surface/.../previews/hero.png",
        "iso": "/assets/surface/.../previews/iso.png",
        "top": "/assets/surface/.../previews/top.png",
        "side": "/assets/surface/.../previews/side.png"
      },
      "job_json": "/assets/surface/.../job.json"
    }
  }
}

URL Rules (Strict)

GlyphEngine returns ONLY relative URLs for public assets.

Frontend, backend, and assistant MUST resolve absolute URLs via configuration.

This guarantees compatibility with:

nginx

reverse proxies

Cloudflare caching

future domain / path changes

Subfolder Rules

subfolder is optional.

If provided, it MUST be sanitized to a single folder name.

Allowed

Letters (a–z, A–Z)

Numbers (0–9)

Dash (-)

Underscore (_)

Forbidden

Slashes (/)

Dots (.)

Traversal sequences (..)

Whitespace

Invalid subfolder values MUST be ignored or replaced with a sanitized fallback.

Assistant Permissions

The HexForge Assistant (and agent tools) MAY:

Create jobs

Poll job status

Read public asset paths

The Assistant MUST NOT:

Write files directly

Modify completed jobs

Access internal-only directories

Bypass the Surface v1 API contract

Contract Stability

This document is authoritative for Surface v1.

Breaking changes require:

A new API version

A new asset namespace

A new interface document


---

### Why this is now “locked”
- Name confusion eliminated (GlyphEngine vs Surface API)
- Ports, URLs, and behavior exactly match your live nginx + Docker setup
- Explicit future-proofing for agents, new engines, and v2 work

Send the **next doc** when ready.