"""Trial side A: opens a room via MCP, posts a challenge, verifies B's computed answer, ends the room."""
import sys, json, time, hashlib, secrets, re, signal
sys.path.insert(0, __import__("os").path.dirname(__file__))
from mcpclient import McpClient

url, handoff = sys.argv[1], sys.argv[2]
token = "trial-" + secrets.token_hex(4)
expect = hashlib.sha256(token.encode()).hexdigest()[:12]
try:
    a = McpClient(url, "trial-side-a")
except Exception as e:
    print(f"A: cannot reach the MCP endpoint at {url} ({type(e).__name__}: {e}) - check the URL and your network, then rerun", flush=True)
    sys.exit(1)

# Convert SIGTERM (timeout(1), orchestrated runners) into a clean exit so the
# try/finally below still closes the room; Ctrl-C raises KeyboardInterrupt the same way.
signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
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
print(f"A: room {uin} created via acq_create_room; challenge token handed off out-of-band (file = the existing shared channel)", flush=True)
deadline = time.time() + 300
answer = None
try:
    while time.time() < deadline:
        msgs = a.call("acq_recv", {"uin": uin, "token": toka, "wait": 60})
        mver = re.search(r"VERDICT\s+([0-9a-f]{12})", str(msgs))
        if mver:
            answer = mver.group(1)
            break
finally:
    if not answer:
        # Never leak an active room from a failed or interrupted trial:
        # close it best-effort on the way out.
        try:
            a.call("acq_send", {"uin": uin, "token": toka, "text": "trial aborted - closing room", "end": True})
            print(f"A: room {uin} closed (trial did not complete)", flush=True)
        except Exception:
            print(f"A: WARNING - room {uin} may still be open until it expires; close it with acq_send end=true", flush=True)
if not answer:
    print("A: FAIL - no verdict within 300s"); sys.exit(1)
got = answer
ok = got == expect
a.call("acq_send", {"uin": uin, "token": toka, "text": f"verdict {'accepted' if ok else 'REJECTED'}: expected {expect}, got {got}", "end": True})
print(f"A: {'PASS' if ok else 'FAIL'} - B computed sha256[:12] correctly ({got} == {expect})" if ok else f"A: FAIL mismatch {got} != {expect}", flush=True)
sys.exit(0 if ok else 1)
