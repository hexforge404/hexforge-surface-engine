# HexForge Surface Engine – Integration Report

## Executive summary

HexForge Surface Engine (HSE) is a texture-first surface and enclosure generation service for fabrication workflows.
It produces heightmaps, parametric enclosure geometry (STL), and preview images, and exposes them via a stable public filesystem contract.

The purpose of this report is to lock down filesystem paths, URLs, and proxy routing so the service can be integrated without ambiguity.

---

## Authoritative filesystem contract

All public HSE outputs MUST live under:

/assets/surface/<subfolder?>/<job_id>/

Where:
- <subfolder> is optional (product or project grouping)
- <job_id> is unique per job

### Canonical layout

/assets/surface/
  └── <subfolder?>/
      └── <job_id>/
          ├── job.json
          ├── previews.json
          ├── enclosure/
          │   └── enclosure.stl
          ├── textures/
          │   ├── texture.png
          │   └── heightmap.png
          └── previews/
              ├── hero.png
              ├── iso.png
              ├── top.png
              └── side.png

Everything under /assets/surface is public and nginx-served.

---

## Disk ↔ nginx ↔ URL mapping

Host root:
/mnt/hdd-storage/ai-tools/engines/hexforge3d/

- Surface assets: surface/
- Heightmap assets (existing): output/

| Purpose | Host Path | nginx Path | Public URL |
|-------|----------|------------|------------|
| Surface | /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface | /var/www/hexforge3d/surface | /assets/surface/ |
| Heightmap | /mnt/hdd-storage/ai-tools/engines/hexforge3d/output | /var/www/hexforge3d/output | /assets/heightmap/ |

---

## API routing

HSE runs internally on port 8092.

nginx must proxy:
/api/surface/ → surface-engine:8092/api/surface/

Swagger docs must be reachable at:
/api/surface/docs

---

## Integration verification

- POST /api/surface/jobs creates a job
- Files appear on disk under surface/<job_id>/
- Files are retrievable via /assets/surface/...
- /api/surface/docs loads through nginx

---

## Rollback

To rollback integration:
- Remove surface-engine from docker-compose
- Remove nginx /api/surface and /assets/surface blocks
- Delete surface output directory if it only contains test data
