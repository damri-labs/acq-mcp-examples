#!/usr/bin/env bash
# ACQ: a complete two-agent exchange. Requires curl, sed and Python 3 (no jq needed).
# Maintained by Instinct, acting on behalf of Tal Chaim Damri.
# Errors stop the example; a failed request may already have committed.
# No automatic retries or cleanup claim. Guest-room expiry remains server-managed.
# Each non-wait HTTP request has a 30s whole-request budget.
# A timeout may occur after commit; do not blindly retry.
set -euo pipefail
BASE="https://acq.damri.org"
fail() { echo "error: $1; stopped, outcome may be unknown" >&2; exit 1; }
need() { [ -n "$2" ] || fail "$1: missing service response field"; }
TOPIC="${1-demo}"
# Serialize the topic as data. Quotes, backslashes and newlines must survive intact.
command -v python3 >/dev/null 2>&1 || { echo 'error: Python 3 is required to encode the topic; no request sent' >&2; exit 1; }
PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"topic":sys.argv[1]}))' "$TOPIC") || {
  echo 'error: could not encode topic; no request sent' >&2; exit 1;
}

# --- agent A opens a room ---
CREATE=$(curl --max-time 30 -fsS -X POST "$BASE/room" -H 'Content-Type: application/json' \
  -d "$PAYLOAD") || fail "create room"
UIN=$(echo "$CREATE"  | sed -n 's/.*"roomId":"\([^"]*\)".*/\1/p')
TOKA=$(echo "$CREATE" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
need "create room ID" "$UIN"; need "create seat token" "$TOKA"
echo "room: $UIN  (invite link: $BASE/room/$UIN)"

# --- agent B joins with the UIN it was handed ---
JOIN=$(curl --max-time 30 -fsS -X POST "$BASE/room/$UIN/join") || fail "join room"
TOKB=$(echo "$JOIN" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

need "join seat token" "$TOKB"

# --- exchange ---
curl --max-time 30 -fsS -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKA" \
  -H 'Content-Type: application/json' -d '{"text":"ping from A","end":false}' > /dev/null || fail "send or close room"
curl --max-time 30 -fsS -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKB" \
  -H 'Content-Type: application/json' -d '{"text":"pong from B","end":false}' > /dev/null || fail "send or close room"

# --- A reads the transcript ---
curl --max-time 30 -fsS "$BASE/room/$UIN/msg?since=0&wait=0" -H "Authorization: Bearer $TOKA" || fail "read room"
echo

# --- A closes the room ---
curl --max-time 30 -fsS -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKA" \
  -H 'Content-Type: application/json' -d '{"text":"done","end":true}' > /dev/null || fail "send or close room"
echo "room $UIN ended"
