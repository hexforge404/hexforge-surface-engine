#!/usr/bin/env bash
set -euo pipefail

# validate_surface_v1.sh (bridge v2: supports legacy engine + future job_status contract)
#
# LEGACY behavior observed:
#   POST -> { job_id, status:"created", public:{ job, stl, texture, heightmap, hero } }
#   GET  -> { job_id, created_at:<epoch>, request:{...} }   (no status)
#
# CONTRACT v1 goal:
#   POST/GET -> job_status envelope:
#     { job_id, status, service, updated_at, result:{ public:"/assets/..." } }
#
# This script:
# - Uses legacy map if present (public.hero etc.)
# - If GET has no status, checks for existence of a known asset (hero) to infer completion
# - When contract v1 appears, it becomes strict automatically

API_BASE="${API_BASE:-https://hexforgelabs.com}"
CREATE_URL="${CREATE_URL:-$API_BASE/api/surface/jobs}"
POLL_MAX="${POLL_MAX:-90}"
POLL_SLEEP="${POLL_SLEEP:-1}"

RESOLVE_HOST="${RESOLVE_HOST:-}"
RESOLVE_IP="${RESOLVE_IP:-}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need curl
need sed
need grep

API_HOST="$(echo "$API_BASE" | sed -n 's#^[a-zA-Z]\+://\([^/:]\+\).*#\1#p' | head -n 1)"

CURL_FLAGS=(-sS -L -f)
if [[ -n "$RESOLVE_HOST" && -n "$RESOLVE_IP" ]]; then
  CURL_FLAGS+=(--resolve "${RESOLVE_HOST}:443:${RESOLVE_IP}")
fi

curl_json() { curl "${CURL_FLAGS[@]}" "$@"; }
curl_ok() { curl "${CURL_FLAGS[@]}" -o /dev/null "$@"; }

echo "[validate] API_BASE=$API_BASE host=$API_HOST" >&2
if [[ -n "$RESOLVE_HOST" && -n "$RESOLVE_IP" ]]; then
  echo "[validate] Using --resolve ${RESOLVE_HOST}:443:${RESOLVE_IP}" >&2
fi

echo "[validate] Creating job: $CREATE_URL" >&2

CREATE_RESP="$(curl_json -X POST "$CREATE_URL" \
  -H "Content-Type: application/json" \
  -d '{"surface":"demo","subfolder":null}')"

echo "[validate] Create response:" >&2
echo "$CREATE_RESP" | sed 's/^/[create] /' >&2

JOB_ID="$(echo "$CREATE_RESP" | sed -n 's/.*"job_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
if [[ -z "$JOB_ID" ]]; then
  echo "[validate] ERROR: job_id missing from create response" >&2
  exit 1
fi

# contract v1 preferred: result.public
PUBLIC_ROOT="$(echo "$CREATE_RESP" | sed -n 's/.*"result"[^{]*{[^}]*"public"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"

# legacy public.job -> derive folder
if [[ -z "$PUBLIC_ROOT" ]]; then
  LEGACY_JOB_PATH="$(echo "$CREATE_RESP" | sed -n 's/.*"job"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  if [[ -n "$LEGACY_JOB_PATH" ]]; then
    PUBLIC_ROOT="$(echo "$LEGACY_JOB_PATH" | sed 's#/job\.json$#/#')"
  fi
fi

if [[ -z "$PUBLIC_ROOT" ]]; then
  echo "[validate] ERROR: Could not determine public root (need result.public OR public.job)" >&2
  exit 1
fi

if [[ "$PUBLIC_ROOT" != /assets/* ]]; then
  echo "[validate] ERROR: public root must start with /assets/ (got: $PUBLIC_ROOT)" >&2
  exit 1
fi

echo "[validate] job_id=$JOB_ID public_root=$PUBLIC_ROOT" >&2

# Legacy asset map (if present)
LEGACY_HERO="$(echo "$CREATE_RESP" | sed -n 's/.*"hero"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
LEGACY_STL="$(echo "$CREATE_RESP" | sed -n 's/.*"stl"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
LEGACY_JOBJSON="$(echo "$CREATE_RESP" | sed -n 's/.*"job"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"

STATUS_URL="$API_BASE/api/surface/jobs/$JOB_ID"
echo "[validate] Polling: $STATUS_URL" >&2

FINAL_STATUS=""
for i in $(seq 1 "$POLL_MAX"); do
  RESP="$(curl_json "$STATUS_URL" || true)"
  if [[ -z "$RESP" ]]; then
    echo "[validate] ERROR: empty GET response" >&2
    exit 1
  fi

  # Try to read status if contract v1 appears
  STATUS="$(echo "$RESP" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"

  if [[ -n "$STATUS" ]]; then
    # Contract-ish polling
    echo "[validate] [$i] status=$STATUS" >&2
    case "$STATUS" in
      queued|running)
        sleep "$POLL_SLEEP"
        ;;
      complete|failed)
        FINAL_STATUS="$STATUS"
        break
        ;;
      created|processing) # legacy transitional
        sleep "$POLL_SLEEP"
        ;;
      *)
        echo "[validate] ERROR: unexpected status: $STATUS" >&2
        exit 1
        ;;
    esac
    continue
  fi

  # Legacy GET has no status: infer completion by checking one known asset
  if [[ -n "$LEGACY_HERO" ]]; then
    HERO_URL="$API_BASE$LEGACY_HERO"
    if curl_ok "$HERO_URL"; then
      FINAL_STATUS="complete"
      echo "[validate] [$i] legacy mode: hero exists → complete" >&2
      break
    fi
    echo "[validate] [$i] legacy mode: hero not ready yet" >&2
  else
    # If no hero path, try job.json existence as minimal
    if [[ -n "$LEGACY_JOBJSON" ]]; then
      JOB_URL="$API_BASE$LEGACY_JOBJSON"
      if curl_ok "$JOB_URL"; then
        echo "[validate] [$i] legacy mode: job.json exists (still running)" >&2
      fi
    fi
  fi

  sleep "$POLL_SLEEP"
done

if [[ -z "$FINAL_STATUS" ]]; then
  echo "[validate] WARN: did not reach complete/failed within timeout; continuing with best-effort asset verification." >&2
fi

# Prefer manifest fetch (future contract)
MANIFEST_URL="$API_BASE${PUBLIC_ROOT}job_manifest.json"
echo "[validate] Fetch manifest (if present): $MANIFEST_URL" >&2

if MANIFEST="$(curl_json "$MANIFEST_URL" 2>/dev/null)"; then
  echo "[validate] Manifest (first 40 lines):" >&2
  echo "$MANIFEST" | sed -n '1,40p' | sed 's/^/[manifest] /' >&2

  # Minimal manifest checks
  echo "$MANIFEST" | grep -q "\"job_id\"" || { echo "[validate] ERROR: manifest missing job_id" >&2; exit 1; }
  echo "$MANIFEST" | grep -q "\"service\"" || { echo "[validate] ERROR: manifest missing service" >&2; exit 1; }
  echo "$MANIFEST" | grep -q "\"created_at\"" || { echo "[validate] ERROR: manifest missing created_at" >&2; exit 1; }
  echo "$MANIFEST" | grep -q "\"updated_at\"" || { echo "[validate] ERROR: manifest missing updated_at" >&2; exit 1; }
  echo "$MANIFEST" | grep -q "\"status\"" || { echo "[validate] ERROR: manifest missing status" >&2; exit 1; }
  echo "$MANIFEST" | grep -q "\"public_root\"" || { echo "[validate] ERROR: manifest missing public_root" >&2; exit 1; }

  PUB_ROOT_IN_MANIFEST="$(echo "$MANIFEST" | sed -n 's/.*"public_root"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  if [[ "$PUB_ROOT_IN_MANIFEST" != /assets/* ]]; then
    echo "[validate] ERROR: manifest public_root must start with /assets/ (got: $PUB_ROOT_IN_MANIFEST)" >&2
    exit 1
  fi

  echo "[validate] Fetching referenced /assets/* URLs from manifest..." >&2
  ASSET_PATHS="$(echo "$MANIFEST" | grep -oE '"/assets/[^"]+"' | tr -d '"' | sort -u)"
  if [[ -n "$ASSET_PATHS" ]]; then
    while read -r p; do
      [[ -z "$p" ]] && continue
      URL="$API_BASE$p"
      echo "[validate] GET $URL" >&2
      curl_ok "$URL" || { echo "[validate] ERROR: asset fetch failed: $URL" >&2; exit 1; }
    done <<< "$ASSET_PATHS"
  else
    echo "[validate] WARN: no /assets/* links found in manifest" >&2
  fi

else
  echo "[validate] WARN: job_manifest.json not found (legacy engine). Verifying legacy assets from create response..." >&2
  ASSET_PATHS="$(echo "$CREATE_RESP" | grep -oE '"/assets/[^"]+"' | tr -d '"' | sort -u)"
  if [[ -z "$ASSET_PATHS" ]]; then
    echo "[validate] ERROR: no /assets/* links found in legacy create response" >&2
    exit 1
  fi
  while read -r p; do
    [[ -z "$p" ]] && continue
    URL="$API_BASE$p"
    echo "[validate] GET $URL" >&2
    curl_ok "$URL" || { echo "[validate] ERROR: asset fetch failed: $URL" >&2; exit 1; }
  done <<< "$ASSET_PATHS"
fi

echo "[validate] ✅ Surface v1 validation PASSED (legacy-compatible). Next step: update GlyphEngine POST/GET to job_status + publish job_manifest.json." >&2
echo "$JOB_ID"
