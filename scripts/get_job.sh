#!/usr/bin/env bash
set -euo pipefail

JOB_ID="${1:?usage: get_job.sh <job_id>}"
API_BASE="${API_BASE:-https://hexforgelabs.com}"
RESOLVE_HOST="${RESOLVE_HOST:-}"
RESOLVE_IP="${RESOLVE_IP:-}"

CURL_FLAGS=(-sS -L)
if [[ -n "$RESOLVE_HOST" && -n "$RESOLVE_IP" ]]; then
  CURL_FLAGS+=(--resolve "${RESOLVE_HOST}:443:${RESOLVE_IP}")
fi

curl "${CURL_FLAGS[@]}" "$API_BASE/api/surface/jobs/$JOB_ID"
echo
