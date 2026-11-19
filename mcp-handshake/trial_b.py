"""Trial side B: independent client. Only input is the room UIN from the handoff channel; computes the answer itself."""
import sys, json, time, hashlib, re
sys.path.insert(0, __import__("os").path.dirname(__file__))
from mcpclient import McpClient

url, handoff = sys.argv[1], sys.argv[2]
deadline = time.time() + 240
h = None
print(f"B: waiting for side A's room (handoff file {handoff}) - start trial_a.py first; this waits up to 240s", flush=True)
waited = 0
while time.time() < deadline:
    try:
        h = json.load(open(handoff)); break
    except Exception:
        time.sleep(5); waited += 5
        if waited % 30 == 0:
            print(f"B: still waiting ({waited}s) - is trial_a.py running and did it print its room line?", flush=True)
if not h:
    print("B: FAIL - no handoff after 240s. Start trial_a.py first, with the SAME handoff path, and check it printed its room line.", flush=True)
    sys.exit(1)
b = McpClient(url, "trial-side-b")
joined = b.call("acq_join_room", {"uin": h["uin"]})
def find(d, key):
    if isinstance(d, dict):
        if key in d: return d[key]
        for v in d.values():
            r = find(v, key)
            if r is not None: return r
    try:
        return find(json.loads(d), key)
    except Exception:
        return None
tokb = find(joined, "token") or find(json.loads(joined) if isinstance(joined, str) else {}, "token")
msg = b.call("acq_recv", {"uin": h["uin"], "token": tokb, "wait": 30})
m = re.search(r"trial-[0-9a-f]{8}", str(msg))
if not m: print("B: FAIL - challenge token not found in room text"); sys.exit(1)
digest = hashlib.sha256(m.group(0).encode()).hexdigest()[:12]
b.call("acq_send", {"uin": h["uin"], "token": tokb, "text": f"VERDICT {digest}"})
print(f"B: joined {h['uin']} via acq_join_room, read challenge via acq_recv, computed sha256 locally, replied VERDICT {digest}", flush=True)
