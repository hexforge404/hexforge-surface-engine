# Quick Start — HexForge GlyphEngine (Surface v1)

## What is GlyphEngine? (Surface v1)

**HexForge GlyphEngine** is a headless microservice that generates
texture-driven surface assets (heightmaps) and applies them to parametric
enclosures, producing STL files and preview images.

It implements the **Surface v1 API**, outputs publicly served assets under
`/assets/surface/...`, and is designed to be reverse-proxied through the
main HexForge nginx stack.

---

## Prerequisites

### Local Development
- Python **3.11+**
- pip + venv

### Deployment
- Docker
- Docker Compose

### Shared Host Assets Folder
This path is **authoritative** and must exist on the host:

/mnt/hdd-storage/ai-tools/engines/hexforge3d/surface

yaml
Copy code

---

## Local Development Run

```bash
cd /mnt/hdd-storage/hexforge-glyphengine

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SURFACE_OUTPUT_DIR=/tmp/hexforge-surface
export SURFACE_PUBLIC_PREFIX=/assets/surface

uvicorn hse.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8092
Open:

API docs: http://localhost:8092/docs

Docker Run (Recommended / Production)
1) Ensure host output folder exists
bash
Copy code
sudo mkdir -p /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
sudo chown -R devuser:devuser /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
⚠️ This directory is mounted into the container and served by nginx.
Incorrect permissions WILL cause silent failures.

2) Start the GlyphEngine service
bash
Copy code
cd /mnt/hdd-storage/hexforge-store
docker compose up -d --build surface-engine
Note:
The service name remains surface-engine for compatibility, even though
the repository and container implement GlyphEngine.

3) nginx-provided endpoints
Once running, nginx exposes:

API:
/api/surface/...

Swagger docs:
/api/surface/docs

Public assets:
/assets/surface/...

Smoke Tests
Create a job
bash
Copy code
curl -X POST https://localhost/api/surface/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "subfolder": "demo",
    "enclosure": {
      "inner_mm": [70, 40, 18],
      "wall_mm": 2.4
    },
    "texture": {
      "prompt": "circuit board"
    }
  }'
Verify API docs
bash
Copy code
curl -I https://localhost/api/surface/docs
Expected:

HTTP/2 200

Verify generated assets
bash
Copy code
curl -I https://localhost/assets/surface/demo/<job_id>/job.json
Expected:

HTTP/2 200

Content-Type: application/json

Common Failure Modes
403 / 404 on assets

Check host folder permissions

Confirm nginx alias path matches /var/www/hexforge3d/surface

Jobs never complete

Check container logs

Verify Blender / CadQuery dependencies

Docs load but POST fails

Validate request body matches Surface v1 contract

Stability Note
This document applies to Surface v1 only.

Breaking changes require:

A new API prefix

A new asset namespace

A new Quick Start document

yaml
Copy code

---

### Next up (recommended order)
1. `INTEGRATION_REPORT.md`
2. `FILESYSTEM.md`
3. `ARCHITECTURE.md`