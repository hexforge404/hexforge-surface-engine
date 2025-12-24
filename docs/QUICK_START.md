# Quick Start – HexForge Surface Engine

## What is HSE? (3–5 lines)

HexForge Surface Engine (HSE) is a microservice that generates surface textures (heightmaps) and applies them to parametric enclosures, producing STL files and preview images.
It outputs publicly-served assets under /assets/surface/... and is designed to be reverse-proxied through the main HexForge nginx.

---

## Prereqs

- Python 3.10+ (local dev)
- Docker + docker compose (deployment)
- Shared host assets folder:
  /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface

---

## Local dev run

```bash
cd /mnt/hdd-storage/hexforge-surface-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SURFACE_OUTPUT_DIR=/tmp/hse-surface
export SURFACE_PUBLIC_PREFIX=/assets/surface

uvicorn hse.main:app --reload --host 0.0.0.0 --port 8092
```

Open:
- http://localhost:8092/docs

---

## Docker run (recommended integration)

1) Ensure host output folder exists:

```bash
sudo mkdir -p /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
sudo chown -R $(id -u):$(id -g) /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
```

2) Start the surface-engine service:

```bash
cd /mnt/hdd-storage/hexforge-store
docker compose up -d --build surface-engine
```

3) nginx provides:
- API: /api/surface/...
- Docs: /api/surface/docs
- Files: /assets/surface/...

---

## Smoke tests

```bash
curl -X POST https://localhost/api/surface/jobs \
  -H "Content-Type: application/json" \
  -d '{"subfolder":"demo","enclosure":{"inner_mm":[70,40,18],"wall_mm":2.4},"texture":{"prompt":"circuit board"}}'
```

Verify docs:

```bash
curl -I https://localhost/api/surface/docs
```

Verify assets:

```bash
curl -I https://localhost/assets/surface/demo/<job_id>/job.json
```
