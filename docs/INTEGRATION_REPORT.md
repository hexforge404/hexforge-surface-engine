# HexForge GlyphEngine — Integration Report (Surface v1)

## Executive Summary

**HexForge GlyphEngine** is a texture-first surface and enclosure generation
service for fabrication workflows.

GlyphEngine implements the **Surface v1 API**, producing:

- Displacement-ready heightmaps
- Parametric enclosure geometry (STL + handoff formats)
- Preview images for UI, listings, and documentation

All outputs are exposed through a **stable, publicly served filesystem
contract**. This report locks down filesystem paths, URLs, and proxy routing so
the service can be integrated without ambiguity.

---

## Authoritative Filesystem Contract

All **public Surface v1 outputs** MUST live under:

/assets/surface/<subfolder?>/<job_id>/

yaml
Copy code

Where:
- `<subfolder>` is optional (product or project grouping)
- `<job_id>` is unique per job

Anything outside this tree is **internal-only** and MUST NOT be referenced
by public URLs.

---

## Canonical Layout

/assets/surface/
└── <subfolder?>/
└── <job_id>/
├── job.json
├── previews.json
├── enclosure/
│ └── enclosure.stl
├── textures/
│ ├── texture.png
│ └── heightmap.png
└── previews/
├── hero.png
├── iso.png
├── top.png
└── side.png

yaml
Copy code

Everything under `/assets/surface` is:
- Public
- Read-only
- Served directly by nginx
- Cacheable via Cloudflare

---

## Disk ↔ nginx ↔ URL Mapping

### Host Root (Authoritative)

/mnt/hdd-storage/ai-tools/engines/hexforge3d/

swift
Copy code

Subdirectories:
- `surface/` — Surface v1 public outputs (GlyphEngine)
- `output/` — Legacy / standalone heightmap outputs

### Mapping Table

| Purpose     | Host Path                                                | nginx Path                   | Public URL            |
|------------|-----------------------------------------------------------|------------------------------|-----------------------|
| Surface v1 | /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface       | /var/www/hexforge3d/surface  | /assets/surface/      |
| Heightmap  | /mnt/hdd-storage/ai-tools/engines/hexforge3d/output        | /var/www/hexforge3d/output   | /assets/heightmap/    |

This mapping is **authoritative** and MUST NOT be changed without a new API
version.

---

## API Routing

GlyphEngine runs internally on port **8092**.

nginx MUST proxy:

/api/surface/ → hexforge-glyphengine:8092/api/surface/

yaml
Copy code

Swagger / OpenAPI documentation MUST be reachable at:

/api/surface/docs

yaml
Copy code

---

## Integration Verification Checklist

Integration is considered valid when:

- `POST /api/surface/jobs` successfully creates a job
- Job files appear on disk under:
surface/<subfolder?>/<job_id>/

diff
Copy code
- Generated files are retrievable via:
/assets/surface/...

markdown
Copy code
- `/api/surface/docs` loads correctly through nginx

If any of the above fail, the integration is **invalid**.

---

## Rollback Procedure

To fully rollback GlyphEngine (Surface v1):

1. Remove `surface-engine` from `docker-compose.yml`
2. Remove nginx blocks for:
 - `/api/surface`
 - `/assets/surface`
3. Delete the surface output directory **only if it contains test data**:
/mnt/hdd-storage/ai-tools/engines/hexforge3d/surface

yaml
Copy code

---

## Stability Guarantee

This document defines the **Surface v1 integration contract**.

Breaking changes require:
- A new API prefix
- A new asset namespace
- A new integration report