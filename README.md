# hexforge-glyphengine
## Surface v1 (Frozen)

Surface v1 is frozen/immutable.

- `/api/surface` is permanent
- `/assets/surface` is permanent
- No breaking changes are allowed in v1
- Any breaking change requires a v2 namespace and contracts (e.g. `/api/surface/v2`)


hexforge-glyphengine
 (HGE) is a texture-first surface and enclosure generation engine for fabrication workflows.

# HexForge GlyphEngine

**HexForge GlyphEngine** is a texture-first surface and enclosure generation
engine for fabrication workflows.


GlyphEngine implements the **Surface v1 API**, which focuses on generating
repeatable, displacement-ready surface detail and parametric enclosures for
3D printing, CNC, and hybrid CAD workflows.

## Quickstart (Surface v1.1)

1. Start the API (example):
  - `uvicorn hse.main:app --host 0.0.0.0 --port 8092`
2. Create a job (returns queued job_status):
  - `JOB_ID=$(curl -sk -X POST http://127.0.0.1:8092/api/surface/jobs -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")`
3. Run the worker (writes placeholders, marks complete):
  - `python scripts/run_surface_worker.py "$JOB_ID"`
4. Inspect status and manifest:
  - `curl -sk "http://127.0.0.1:8092/api/surface/jobs/$JOB_ID"`
  - `curl -sk "http://127.0.0.1:8092/api/surface/jobs/$JOB_ID/manifest"`
5. Public assets (served by NGINX):
  - `http://127.0.0.1:8092/assets/surface/$JOB_ID/job_manifest.json`

### Filesystem layout

- `/data/hexforge3d/surface/<job_id>/`
  - `previews/{hero,iso,top,side}.png`
  - `textures/{texture.png,heightmap.png}`
  - `enclosure/enclosure.stl`
  - `job.json` (service doc) and `job_manifest.json` (contract)

### Preview rendering (hero)

- `previews/hero.png` is rendered deterministically from the final displaced STL.
- Implementation uses headless matplotlib + trimesh: centers on the mesh centroid, fixed isometric camera, dark background, simple key lighting, and per-face shading from normals.
- If the STL is missing/invalid or the resulting image is effectively flat (very low pixel variance), the job fails instead of marking complete.

### Heightmap inputs

- Jobs must provide a `heightmap_url` (or `heightmap.url`) param; the worker downloads it into `inputs/input_heightmap.png` and reuses it as `textures/heightmap.png` with checksum + dimensions recorded in `outputs`.
- If the heightmap is missing or empty, the job fails. There is no placeholder/fallback heightmap.

### Contracts and validation

- All envelopes validate against `schemas/common` via `hexforge_contracts`.
- `job_id` must be filesystem-safe (`A-Za-z0-9_-`, min 3 chars).
- Manifest version is fixed to `"v1"`; service is `"hexforge-glyphengine"`.

### Acceptance checklist

```
JOB_ID=$(curl -sk -X POST https://hexforgelabs.com/api/surface/jobs \
  -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

docker exec -it hexforge-glyphengine \ 
  python3 /app/scripts/run_surface_worker.py "$JOB_ID"

curl -sk "https://hexforgelabs.com/api/surface/jobs/$JOB_ID"
curl -sk "https://hexforgelabs.com/api/surface/jobs/$JOB_ID/manifest"
curl -sk "https://hexforgelabs.com/assets/surface/$JOB_ID/job_manifest.json"
```

Expected: status moves to `complete`, asset URLs resolve, schemas validate.



## Primary Outputs

- Displacement-ready texture assets  
  (heightmaps, with optional normals and masks)
- Parametric enclosure geometry  
  (STL for printing, plus Blender / CAD-friendly handoff formats)
- Preview renders suitable for:
  - Product listings
  - Documentation
  - Social and marketing assets


## Stack Integration

GlyphEngine is designed as a **headless engine** within the HexForge stack:

- **Frontend UI**
  - Job creation
  - Preview display
  - Asset downloads
- **Backend API Gateway**
  - Authentication
  - Persistence
  - Routing
- **HexForge Assistant**
  - Job orchestration
  - Parameter validation
  - Workflow helpers
  - Multi-engine coordination (future)

## Core Focus (Surface v1)

- Diffusion-based texture generation → heightmap output
- UV-displacement workflow for applying textures to enclosure surfaces
  (non-destructive, CAD-friendly)
- Parametric enclosure generation (CadQuery-first)
- Stable filesystem layout and public URLs for all generated assets


## Explicit Non-Goals (Surface v1)

The following are intentionally **out of scope** for v1:

- Full AI text-to-3D mesh generation
- G-code generation or slicer replacement
- Complex CAD editing UI
- Marketplace or community features

These may be addressed by **future engines**, not GlyphEngine itself.


## High-Level Pipeline

1. User defines enclosure parameters and style prompt
2. Texture generator creates base pattern image(s)
3. Texture processor produces heightmap
   (and optional normals / masks)
4. Enclosure generator produces:
   - Base geometry
   - Mapping references
5. Outputs and previews are written to canonical public asset folders
6. UI displays previews and exposes downloadable assets


## Naming Clarification

- **Repository / Service name:** HexForge GlyphEngine
- **API + asset namespace:** Surface v1 (`/api/surface`, `/assets/surface`)
- **Reason:**  
  GlyphEngine is the *engine family*.  
  Surface v1 is the *first public contract*.

This preserves backward compatibility while allowing future engines
(e.g. Relief, Pattern, Lattice, Panel) to coexist cleanly.
