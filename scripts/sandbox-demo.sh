#!/usr/bin/env bash
# End-to-end: two users' bots, mutual approve, message exchange.
set -euo pipefail
BASE="${SANDBOX_URL:-http://127.0.0.1:8080}"

json() { python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))'; }

echo "== health =="
curl -fsS "$BASE/v0/health" | json

echo "== register alice bot =="
ALICE=$(curl -fsS -X POST "$BASE/v0/bots/register" -H 'content-type: application/json' \
  -d '{"user_handle":"alice","bot_handle":"alice-bot","display_name":"Alice Bot"}')
echo "$ALICE" | json
A_CID=$(echo "$ALICE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_id"])')
A_SEC=$(echo "$ALICE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_secret"])')

echo "== register bob bot =="
BOB=$(curl -fsS -X POST "$BASE/v0/bots/register" -H 'content-type: application/json' \
  -d '{"user_handle":"bob","bot_handle":"bob-bot","display_name":"Bob Bot"}')
echo "$BOB" | json
B_CID=$(echo "$BOB" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_id"])')
B_SEC=$(echo "$BOB" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_secret"])')

token() {
  curl -fsS -X POST "$BASE/v0/oauth/token" -H 'content-type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$1\",\"client_secret\":\"$2\"}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}

A_TOK=$(token "$A_CID" "$A_SEC")
B_TOK=$(token "$B_CID" "$B_SEC")

echo "== alice requests channel with bob-bot =="
CH=$(curl -fsS -X POST "$BASE/v0/channels" -H "authorization: Bearer $A_TOK" -H 'content-type: application/json' \
  -d '{"peer_bot_handle":"bob-bot"}')
echo "$CH" | json
CH_ID=$(echo "$CH" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
STATUS=$(echo "$CH" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
test "$STATUS" = "pending"

echo "== bob approves =="
CH2=$(curl -fsS -X POST "$BASE/v0/channels/$CH_ID/approve" -H "authorization: Bearer $B_TOK" -H 'content-type: application/json' \
  -d '{"scopes":["msg.send","msg.recv","meta.presence"]}')
echo "$CH2" | json
test "$(echo "$CH2" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')" = "open"

echo "== alice sends =="
curl -fsS -X POST "$BASE/v0/channels/$CH_ID/messages" -H "authorization: Bearer $A_TOK" -H 'content-type: application/json' \
  -d '{"text":"hola bob — untrusted peer data"}' | json

echo "== bob sends =="
curl -fsS -X POST "$BASE/v0/channels/$CH_ID/messages" -H "authorization: Bearer $B_TOK" -H 'content-type: application/json' \
  -d '{"text":"hola alice — sandbox ok"}' | json

echo "== bob polls =="
curl -fsS "$BASE/v0/channels/$CH_ID/messages" -H "authorization: Bearer $B_TOK" | json

echo
echo "demo ok · console: $BASE/"
