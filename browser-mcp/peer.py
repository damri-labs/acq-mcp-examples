"""Controlled browser/MCP transport peer. No model calls; no credential logs."""
import json
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://acq.damri.org/mcp"
CONTRACT = ('SYNTHETIC CONTRACT v1: GET /widgets/{id}; 200 returns '
            '{id:string,name:string}; missing widget returns 404 '
            '{error:"not_found"}. Scripted transport check only.')
REPLY = ('SCRIPTED REVIEW B: identifier character rules are unspecified. '
         'Proposed test: unknown widget returns 404. '
         'Prewritten text only; no model or API test was run.')


def decode_tool(reply):
    if not isinstance(reply, dict) or "error" in reply:
        raise ValueError("JSON-RPC error")
    result = reply.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        raise ValueError("MCP tool error or missing result")
    content = result.get("content")
    if not isinstance(content, list):
        raise ValueError("missing MCP content")
    texts = [x.get("text") for x in content
             if isinstance(x, dict) and x.get("type") == "text"]
    if len(texts) != 1 or not isinstance(texts[0], str):
        raise ValueError("expected one text result")
    payload = json.loads(texts[0])
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload


class Client:
    def __init__(self):
        self.request_id = 0
        self.session = None

    def rpc(self, method, params, notify=False):
        self.request_id += 1
        data = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            data["id"] = self.request_id
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": "2025-06-18"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(ENDPOINT, json.dumps(data).encode(), headers)
        with urllib.request.urlopen(req, timeout=45) as response:
            self.session = response.headers.get("Mcp-Session-Id", self.session)
            body = response.read()
        if notify:
            return None
        reply = json.loads(body)
        if not isinstance(reply, dict) or "error" in reply:
            raise ValueError("JSON-RPC error")
        return reply

    def call(self, name, args):
        return decode_tool(self.rpc("tools/call", {"name": name, "arguments": args}))


def exchange(client, uin, confirm=input, emit=print):
    client.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "browser-mcp-scripted-peer", "version": "1"}})
    client.rpc("notifications/initialized", {}, notify=True)
    joined = client.call("acq_join_room", {"uin": uin})
    token = joined.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("join returned no seat token")
    auth = {"uin": uin, "token": token}
    received = client.call("acq_recv", {**auth, "since": 0, "wait": 30})
    if not any(m.get("from") == "A" and m.get("text") == CONTRACT
               for m in received.get("messages", []) if isinstance(m, dict)):
        raise ValueError("expected synthetic contract not received")
    emit("PASS: exact synthetic contract received")
    cid = "scripted-" + uuid.uuid4().hex
    sent = client.call("acq_send", {**auth, "text": REPLY, "cid": cid})
    if sent.get("cid") != cid:
        raise ValueError("send cid mismatch")
    readback = client.call("acq_recv", {**auth, "since": 0, "wait": 0, "self": True, "peek": True})
    if not any(m.get("from") == "B" and m.get("cid") == cid and m.get("text") == REPLY
               for m in readback.get("messages", []) if isinstance(m, dict)):
        raise ValueError("read-back mismatch")
    emit("PASS: send cid and exact reply verified by read-back")
    answer = confirm("Check B's reply in your browser, then End room and Confirm end. Type yes after both: ")
    if answer.strip().lower() != "yes":
        raise ValueError("browser checks not confirmed")
    final = client.call("acq_recv", {**auth, "since": 0, "wait": 0, "self": True, "peek": True})
    if final.get("ended") is not True:
        raise ValueError("room is not ended")
    emit("PASS: operator confirmed browser display; MCP ended=true")


if __name__ == "__main__":
    try:
        room = input("Your deliberately opened guest-room UIN: ").strip()
        if not room:
            raise ValueError("missing UIN")
        exchange(Client(), room)
    except (Exception, KeyboardInterrupt):
        # Do not print exception text: server errors may contain private data.
        print("FAIL: check incomplete. If joined, end your room in the browser. No automatic retry.")
        raise SystemExit(1)
