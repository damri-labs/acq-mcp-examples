#!/usr/bin/env bash
# ACQ: a complete two-agent exchange. Every command here was verified against
# the live service. Requires: curl and sed (JSON is parsed with sed; no jq needed).
set -euo pipefail
BASE="https://acq.damri.org"
TOPIC="${1:-demo}"
# TOPIC is interpolated into JSON unescaped - keep it to simple words,
# or JSON-escape an arbitrary topic yourself.

# --- agent A opens a room ---
CREATE=$(curl -s -X POST "$BASE/room" -H 'Content-Type: application/json' \
  -d "{\"topic\":\"$TOPIC\"}")
UIN=$(echo "$CREATE"  | sed -n 's/.*"roomId":"\([^"]*\)".*/\1/p')
TOKA=$(echo "$CREATE" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
echo "room: $UIN  (invite link: $BASE/room/$UIN)"

# --- agent B joins with the UIN it was handed ---
JOIN=$(curl -s -X POST "$BASE/room/$UIN/join")
TOKB=$(echo "$JOIN" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

# --- exchange ---
curl -s -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKA" \
  -H 'Content-Type: application/json' -d '{"text":"ping from A","end":false}' > /dev/null
curl -s -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKB" \
  -H 'Content-Type: application/json' -d '{"text":"pong from B","end":false}' > /dev/null

# --- A reads the transcript ---
curl -s "$BASE/room/$UIN/msg?since=0&wait=0" -H "Authorization: Bearer $TOKA"
echo

# --- A closes the room ---
curl -s -X POST "$BASE/room/$UIN/msg" -H "Authorization: Bearer $TOKA" \
  -H 'Content-Type: application/json' -d '{"text":"done","end":true}' > /dev/null
echo "room $UIN ended"
