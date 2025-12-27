#!/usr/bin/env bash
set -euo pipefail

PUBLIC_ROOT="${1:?usage: verify_assets.sh </assets/.../>}"
API_BASE="${API_BASE:-https://hexforgelabs.com}"
RESOLVE_HOST="${RESOLVE_HOST:-}"
RESOLVE_IP="${RESOLVE_IP:-}"

CURL_FLAGS=(-sS -L -f)
if [[ -n "$RESOLVE_HOST" && -n "$RESOLVE_IP" ]]; then
  CURL_FLAGS+=(--resolve "${RESOLVE_HOST}:443:${RESOLVE_IP}")
fi

MANIFEST_URL="$API_BASE${PUBLIC_ROOT}job_manifest.json"
echo "[verify] manifest: $MANIFEST_URL" >&2
MANIFEST="$(curl "${CURL_FLAGS[@]}" "$MANIFEST_URL")"

echo "$MANIFEST" | grep -oE '"/assets/[^"]+"' | tr -d '"' | sort -u | while read -r p; do
  [[ -z "$p" ]] && continue
  URL="$API_BASE$p"
  echo "[verify] GET $URL" >&2
  curl "${CURL_FLAGS[@]}" -o /dev/null "$URL"
done

echo "[verify] ✅ assets ok" >&2
