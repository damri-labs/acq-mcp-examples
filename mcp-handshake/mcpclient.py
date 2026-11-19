"""Minimal streamable-HTTP MCP client (stdlib only) - one instance per agent client."""
import json, urllib.request

class McpClient:
    def __init__(self, url, name):
        self.url = url
        self._id = 0
        self._post("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": name, "version": "0.1"}})
        self._notify("notifications/initialized", {})

    def _post(self, method, params):
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        with urllib.request.urlopen(req, timeout=130) as r:
            payload = json.loads(r.read())
        if "error" in payload:
            raise RuntimeError(f"{method} -> {payload['error']}")
        return payload["result"]

    def _notify(self, method, params):
        body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        try:
            urllib.request.urlopen(req, timeout=30)
        except Exception:
            pass  # notifications may return 202/empty

    def call(self, tool, args):
        res = self._post("tools/call", {"name": tool, "arguments": args})
        if res.get("isError"):
            raise RuntimeError(f"{tool} -> {res['content'][0].get('text','')[:300]}")
        return res["content"][0]["text"]
