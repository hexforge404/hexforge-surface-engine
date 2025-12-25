# HexForge GlyphEngine — Surface API (v1)

This service provides a stable "Surface v1" contract:
- API creates "surface jobs"
- Jobs write outputs to a deterministic filesystem layout
- Outputs are served publicly through NGINX under `/assets/surface/...`

## Base URL / Routing

Internal (docker network):
- `http://glyphengine:8092/api/surface`

Public (via site reverse proxy):
- API: `https://hexforgelabs.com/api/surface/...`
- Assets: `https://hexforgelabs.com/assets/surface/...`

## Environment Variables

- `SURFACE_OUTPUT_DIR` (default: `/data/hexforge3d/surface`)
  - Root folder where job outputs are created.
- `SURFACE_PUBLIC_PREFIX` (default: `/assets/surface`)
  - Public URL prefix that maps to the output directory via NGINX `alias`.
- `ROOT_PATH` (default: `/api/surface`)
  - The API prefix for routing (useful behind reverse proxies).

## Endpoints

### GET `/api/surface/health`
Returns service health.

Example response:
```json
{ "ok": true, "service": "hexforge-glyphengine", "api": "surface-v1" }
POST /api/surface/jobs
Creates a new surface job. Returns a job id and public URLs.

Request body:

json
Copy code
{ "subfolder": "demo" }
Response:

json
Copy code
{
  "job_id": "098749bdca7e46b5",
  "subfolder": "demo",
  "status": "created",
  "public": {
    "job": "/assets/surface/demo/<job_id>/job.json",
    "stl": "/assets/surface/demo/<job_id>/enclosure/enclosure.stl",
    "texture": "/assets/surface/demo/<job_id>/textures/texture.png",
    "heightmap": "/assets/surface/demo/<job_id>/textures/heightmap.png",
    "hero": "/assets/surface/demo/<job_id>/previews/hero.png"
  }
}
GET /api/surface/jobs/{job_id}?subfolder=demo
Returns the job.json payload for a job if it exists.

Filesystem Contract
Given:

SURFACE_OUTPUT_DIR=/data/hexforge3d/surface

subfolder=demo

job_id=098749bdca7e46b5

The job root is:

/data/hexforge3d/surface/demo/098749bdca7e46b5/

Expected structure:

css
Copy code
job.json
enclosure/
  enclosure.stl
textures/
  texture.png
  heightmap.png
previews/
  hero.png
  iso.png
  top.png
  side.png
NGINX Asset Mapping (Required)
The public prefix must map to the output directory. Example:

bash
Copy code
location ^~ /assets/surface/ {
  alias /var/www/hexforge3d/surface/;
}
Permissions Requirement
The container runs as a non-root app user and must be able to write to the mounted surface directory.

Recommended host setup:

Create shared group hexforge

Set surface dir to group hexforge

Enable group write + setgid so new files inherit group

bash
Copy code
sudo groupadd -f hexforge
sudo chgrp -R hexforge /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
sudo chmod -R 2775 /mnt/hdd-storage/ai-tools/engines/hexforge3d/surface
Then ensure the container includes group_add: [<hexforge_gid>] (ex: 1001).

bash
Copy code

---

## 3) `smoke_test_surface_v1.sh` (single command validation)

This tests:
- glyphengine health (internal)
- job create (internal)
- job + hero asset fetch through **NGINX public path** (`https://localhost/...`)
- prints the URLs cleanly

```bash
#!/usr/bin/env bash
set -euo pipefail

NGINX_CONT="${NGINX_CONT:-hexforge-nginx}"
GLYPH_HOST="${GLYPH_HOST:-glyphengine}"
GLYPH_PORT="${GLYPH_PORT:-8092}"
SUBFOLDER="${SUBFOLDER:-demo}"

echo "[1/5] Health (internal) ..."
docker exec -it "$NGINX_CONT" sh -lc \
  "curl -fsS http://$GLYPH_HOST:$GLYPH_PORT/api/surface/health | jq"

echo "[2/5] Create job (internal) ..."
JOB_JSON="$(docker exec -it "$NGINX_CONT" sh -lc \
  "curl -fsS -X POST http://$GLYPH_HOST:$GLYPH_PORT/api/surface/jobs \
    -H 'Content-Type: application/json' \
    -d '{\"subfolder\":\"$SUBFOLDER\"}'")"

echo "$JOB_JSON" | jq .

JOB_ID="$(echo "$JOB_JSON" | jq -r '.job_id')"
JOB_URL="$(echo "$JOB_JSON" | jq -r '.public.job')"
HERO_URL="$(echo "$JOB_JSON" | jq -r '.public.hero')"

echo "[3/5] Fetch job.json via NGINX (public path) ..."
docker exec -it "$NGINX_CONT" sh -lc \
  "curl -fsS -k https://localhost$JOB_URL | jq .job_id,.subfolder,.created_at"

echo "[4/5] Fetch hero.png headers via NGINX (public path) ..."
docker exec -it "$NGINX_CONT" sh -lc \
  "curl -fsSI -k https://localhost$HERO_URL | sed -n '1,12p'"

echo "[5/5] DONE ✅"
echo "JOB_ID:   $JOB_ID"
echo "JOB_URL:  $JOB_URL"
echo "HERO_URL: $HERO_URL"
Run it from your host:

bash
Copy code
chmod +x smoke_test_surface_v1.sh
./smoke_test_surface_v1.sh
✅ One small correction to your current compose block
Your line:

yaml
Copy code
group_add:
  - 1001  # docker group for docker-in-docker access
Should be:

yaml
Copy code
group_add:
  - 1001  # hexforge shared FS group (surface write permissions)
Because that’s exactly what fixed the permission issue.

