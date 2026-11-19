"""Trial side A: opens a room via MCP, posts a challenge, verifies B's computed answer, ends the room."""
import sys, json, time, hashlib, secrets, re
sys.path.insert(0, "/tmp/acq_trial")
from mcpclient import McpClient

url, handoff = sys.argv[1], sys.argv[2]
token = "trial-" + secrets.token_hex(4)
expect = hashlib.sha256(token.encode()).hexdigest()[:12]
a = McpClient(url, "trial-side-a")
created = a.call("acq_create_room", {"topic": "mcp-handshake-trial", "join_window_hours": 1,
    "opening_message": f"MCP handshake trial. Reply with exactly 'VERDICT <x>' where x is the first 12 hex chars of sha256 of this token: {token}"})
info = json.loads(created)
# tolerate either shape: find uin + token
def find(d, key):
    if isinstance(d, dict):
        if key in d: return d[key]
        for v in d.values():
            r = find(v, key)
            if r is not None: return r
    return None
uin = find(info, "uin") or find(info, "roomId")
toka = find(info, "token")
with open(handoff, "w") as f: json.dump({"uin": uin, "token": token}, f)
print(f"A: room {uin} created via acq_create_room; challenge token handed off out-of-band (file = the existing shared channel)")
deadline = time.time() + 300
answer = None
while time.time() < deadline:
    msgs = a.call("acq_recv", {"uin": uin, "token": toka, "wait": 60})
    mver = re.search(r"VERDICT\s+([0-9a-f]{12})", str(msgs))
    if mver:
        answer = mver.group(1)
        break
if not answer:
    print("A: FAIL - no verdict within 300s"); sys.exit(1)
got = answer
ok = got == expect
a.call("acq_send", {"uin": uin, "token": toka, "text": f"verdict {'accepted' if ok else 'REJECTED'}: expected {expect}, got {got}", "end": True})
print(f"A: {'PASS' if ok else 'FAIL'} - B computed sha256[:12] correctly ({got} == {expect})" if ok else f"A: FAIL mismatch {got} != {expect}")
sys.exit(0 if ok else 1)
