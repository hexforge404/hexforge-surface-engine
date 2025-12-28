#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8092/api/surface}"

docker exec -i hexforge-glyphengine python - <<PY
import json, urllib.request
from jsonschema import validate
from hexforge_contracts import load_schema
from hse.fs.paths import manifest_path

base = "${BASE}"
status_schema = load_schema("job_status.schema.json")
manifest_schema = load_schema("job_manifest.schema.json")

req = urllib.request.Request(
    f"{base}/jobs",
    data=json.dumps({}).encode("utf-8"),
    headers={"Content-Type":"application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    created = json.loads(r.read().decode("utf-8"))

validate(created, status_schema)
job_id = created["job_id"]
print("OK POST job_status:", job_id)

with urllib.request.urlopen(f"{base}/jobs/{job_id}") as r:
    st = json.loads(r.read().decode("utf-8"))
validate(st, status_schema)
print("OK GET job_status:", job_id, st["status"])

mp = manifest_path(job_id, subfolder=None)
m = json.loads(mp.read_text(encoding="utf-8"))
validate(m, manifest_schema)
print("OK manifest schema:", mp)
PY

echo "✅ contracts verified"
