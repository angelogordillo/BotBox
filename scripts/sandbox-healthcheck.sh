#!/usr/bin/env bash
set -euo pipefail
BASE="${SANDBOX_URL:-http://127.0.0.1:8080}"
curl -fsS "$BASE/v0/health"  | grep -q '"status":"ok"'
echo
echo "sandbox health ok ($BASE)"
