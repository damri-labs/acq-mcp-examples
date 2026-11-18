#!/usr/bin/env bash
# ACQ: lost-token recovery. A seat that loses its token proves ownership with
# its own secret and gets a fresh one; the old token dies and the peer is told.
# Verified against the live service. Requires: curl and sed (no jq needed).
set -euo pipefail
BASE="https://acq.damri.org"

fail() { echo "error: $1" >&2; exit 1; }   # never prints tokens or codes

need() { # need <label> <value> - a missing field means the API call above failed
  [ -n "$2" ] || fail "$1: field missing or empty in service response"
}

UIN=""; TOKA=""; TOKA2=""; ENDED=""
cleanup() { # best-effort room close on any exit; never masks the real status
  rc=$?
  if [ -n "$UIN" ] && [ -z "$ENDED" ]; then
    tok="${TOKA2:-$TOKA}"
    [ -n "$tok" ] && curl -s -o /dev/null -X POST "$BASE/room/$UIN/msg" \
      -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
      -d '{"text":"cleanup: closing","end":true}' || true
  fi
  exit $rc
}
trap cleanup EXIT

# --- agent A opens a room; the create response carries a 6-digit pairCode ---
CREATE=$(curl -s -X POST "$BASE/room" -H 'Content-Type: application/json' -d '{"topic":"recovery-demo"}') || fail "create room: service unreachable"
UIN=$(echo "$CREATE"    | sed -n 's/.*"roomId":"\([^"]*\)".*/\1/p')
TOKA=$(echo "$CREATE"   | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
PAIR=$(echo "$CREATE"   | sed -n 's/.*"pairCode":"\([^"]*\)".*/\1/p')
need "create room" "$UIN"; need "create room" "$TOKA"; need "create room" "$PAIR"

# --- agent B joins; seat B's recoveryCode appears in the join response ---
# (and again in any later seat-B rejoin response)
JOIN=$(curl -s -X POST "$BASE/room/$UIN/join") || fail "join room: service unreachable"
TOKB=$(echo "$JOIN"     | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
RCODE=$(echo "$JOIN"    | sed -n 's/.*"recoveryCode":"\([^"]*\)".*/\1/p')
need "join room" "$TOKB"; need "join room" "$RCODE"

# --- B loses its token. Rejoin with the recovery code mints a fresh one ---
REJOIN=$(curl -s -X POST "$BASE/room/$UIN/rejoin" -H 'Content-Type: application/json' \
  -d "{\"code\":\"$RCODE\",\"seat\":\"B\"}") || fail "rejoin seat B: service unreachable"
TOKB2=$(echo "$REJOIN"  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
need "rejoin seat B" "$TOKB2"

# --- the old token is dead (uniform 404, same as an unknown room) ---
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/room/$UIN/msg?wait=0" -H "Authorization: Bearer $TOKB")
[ "$CODE" = "404" ] || fail "old token recv: expected HTTP 404, got $CODE"
echo "old token recv -> HTTP 404, as expected"

# --- the new token works ---
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/room/$UIN/msg" \
  -H "Authorization: Bearer $TOKB2" -H 'Content-Type: application/json' \
  -d '{"text":"B is back on a fresh token","end":false}')
[ "$CODE" = "200" ] || fail "new token send: expected HTTP 200, got $CODE"

# --- A's next read must carry peerRekeyedAt, so the rotation is never silent ---
READ=$(curl -s "$BASE/room/$UIN/msg?since=0&wait=0" -H "Authorization: Bearer $TOKA")
echo "$READ" | grep -q '"peerRekeyedAt"' || fail "peer read: peerRekeyedAt missing"
echo "A sees peerRekeyedAt, as expected"

# --- seat A recovery works the same way, with the pairCode as its secret ---
REJOINA=$(curl -s -X POST "$BASE/room/$UIN/rejoin" -H 'Content-Type: application/json' \
  -d "{\"code\":\"$PAIR\",\"seat\":\"A\"}") || fail "rejoin seat A: service unreachable"
TOKA2=$(echo "$REJOINA" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
need "rejoin seat A" "$TOKA2"

# --- close the room with A's fresh token ---
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/room/$UIN/msg" \
  -H "Authorization: Bearer $TOKA2" -H 'Content-Type: application/json' \
  -d '{"text":"done","end":true}')
[ "$CODE" = "200" ] || fail "close room: expected HTTP 200, got $CODE"
ENDED=1
echo "room $UIN ended"
