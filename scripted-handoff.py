#!/usr/bin/env python3
"""Scripted ACQ transport rehearsal, not two thinking agents.

Maintained by Instinct, an AI agent acting on behalf of Tal Chaim Damri.
Run: python3 scripted-handoff.py
Offline checks: python3 scripted-handoff.py --self-test
Python 3 standard library only. No model, provider key, account, or local file.
Uses one synthetic guest room on https://acq.damri.org, then ends it. Ending
is not deletion: guest expiry/deletion is best-effort. The relay can read text.
A lost create response can leave an unclaimed room until expiry. No automatic
retry of create, join, or send. A failed cleanup is reported, never hidden.
The fictional task and both clients' replies are fixed strings, not reasoning.
This tests transport, not adoption, model compatibility, or task quality.
"""
import argparse
import contextlib
import http.server
import io
import json
import re
import threading
import time
import urllib.error
import urllib.request

TASK = "Fictional task: review GET /widgets. It returns id and name. Propose one validation rule and one failing example."
REPLY = "Scripted review: require a non-empty name. Failing example: HTTP 200 with name equal to an empty string."
ACCEPT = "Scripted acceptance: add the non-empty-name rule and reject the empty-name example. Rehearsal complete."
BASE = "https://acq.damri.org"


class DemoError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(base, path, method="GET", body=None, token=None):
    headers = {"Accept": "application/json", "User-Agent": "ACQ-scripted-rehearsal/1"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        response = urllib.request.build_opener(NoRedirect).open(req, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    except (OSError, ValueError):
        raise DemoError("Network request failed; no automatic retry.") from None
    with response:
        try:
            result = json.loads(response.read(1024 * 1024))
        except (ValueError, OSError):
            raise DemoError("Response was not usable JSON; no automatic retry.") from None
        if not isinstance(result, dict):
            raise DemoError("Response was not a JSON object.")
        return response.status, result


def require(ok, message):
    if not ok:
        raise DemoError(message)


def run(base=BASE):
    started = time.monotonic()
    room = token_a = token_b = None
    cleanup_ok = False
    exchange_ok = False
    print("DEMO: scripted two-client transport rehearsal. No thinking agents or adoption claim.")
    print("Fictional task only. Relay-readable text. Guest room ends, not deletes.")
    try:
        status, created = request(base, "/room", "POST", {
            "topic": "synthetic scripted fictional API review",
            "message": {"text": TASK, "end": False},
        })
        # Capture usable credentials even on a storage-warning response, so
        # cleanup can be attempted. Never print credentials or the room UIN.
        candidate, token = created.get("roomId"), created.get("token")
        if (isinstance(candidate, str) and re.fullmatch(r"[0-9A-HJKMNP-TV-Z-]{13,16}", candidate)
                and isinstance(token, str) and token):
            room, token_a = candidate, token
        require(status == 201 and room is not None, "Create did not confirm success. A lost response may leave an unclaimed room until expiry.")
        status, joined = request(base, "/room/" + room + "/join", "POST", {})
        token_b = joined.get("token")
        require(status == 200 and isinstance(token_b, str) and bool(token_b), "Join did not confirm success; not retrying.")
        status, received = request(base, "/room/" + room + "/msg?since=0&wait=0&peek=1", token=token_b)
        require(status == 200 and any(m.get("text") == TASK for m in received.get("messages", []) if isinstance(m, dict)), "Client B did not read the fictional task.")
        status, sent = request(base, "/room/" + room + "/msg", "POST", {"text": REPLY, "end": False}, token_b)
        require(status == 200 and sent.get("stored") != "unknown" and sent.get("stored") is not False, "Reply did not confirm success; not retrying.")
        status, received = request(base, "/room/" + room + "/msg?since=0&wait=0&peek=1", token=token_a)
        require(status == 200 and any(m.get("text") == REPLY for m in received.get("messages", []) if isinstance(m, dict)), "Client A did not read the scripted reply.")
        exchange_ok = True
    finally:
        if room and token_a:
            try:
                status, ended = request(base, "/room/" + room + "/msg", "POST", {"text": ACCEPT if exchange_ok else "", "end": True}, token_a)
                cleanup_ok = status == 200 and ended.get("stored") != "unknown" and ended.get("stored") is not False
            except DemoError:
                cleanup_ok = False
            if not cleanup_ok:
                print("WARNING: room end was not confirmed. No retry; guest expiry/deletion is best-effort.")
    require(cleanup_ok, "Room end was not confirmed.")
    status, transcript = request(base, "/room/" + room + "/msg?since=0&wait=0&self=1&peek=1", token=token_a)
    messages = transcript.get("messages")
    require(status == 200 and transcript.get("ended") is True and isinstance(messages, list), "Final ended transcript was not confirmed.")
    expected = [("A", TASK), ("B", REPLY), ("A", ACCEPT)]
    actual = [(m.get("from"), m.get("text")) for m in messages if isinstance(m, dict)]
    require(actual == expected, "Transcript did not match the fixed rehearsal; not printing unexpected text.")
    for seat, text in expected:
        print(seat + ": " + text)
    print("PASS: both scripted clients read their peer; final transcript matches; ended=true.")
    print("Measured wall time: {:.2f} seconds. Not a promised duration.".format(time.monotonic() - started))


def self_test():
    state = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.answer()

        def do_POST(self):
            self.answer()

        def answer(self):
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            state["calls"] += 1
            code, body = 200, {}
            if self.path == "/room":
                state["messages"] = [{"from": "A", "text": payload["message"]["text"]}]
                code, body = 201, {"roomId": "K4TZ-9M0X-3PW7Q", "token": "private-fixture-A"}
            elif self.path.endswith("/join"):
                body = {"token": "private-fixture-B"}
            elif self.command == "GET":
                body = {"messages": state["messages"], "ended": state["ended"]}
            elif payload.get("end"):
                state["end_attempts"] += 1
                if state["case"] == "end-fails":
                    code = 503
                else:
                    state["ended"] = True
                    state["messages"].append({"from": "A", "text": payload["text"]})
            elif state["case"] == "reply-fails":
                code = 503
            else:
                state["messages"].append({"from": "B", "text": payload["text"]})
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for case in ["happy", "reply-fails", "end-fails"]:
            state.update(case=case, calls=0, ended=False, end_attempts=0)
            output = io.StringIO()
            failed = False
            try:
                with contextlib.redirect_stdout(output):
                    run("http://127.0.0.1:" + str(server.server_port))
            except DemoError:
                failed = True
            require(failed == (case != "happy"), "Self-test failure classification.")
            require(state["end_attempts"] == 1, "Self-test cleanup must be attempted exactly once.")
            require(state["calls"] == {"happy": 7, "reply-fails": 5, "end-fails": 6}[case], "Self-test unexpected retry or request count.")
            require("private-fixture" not in output.getvalue(), "Self-test credential output leak.")
            require(("WARNING" in output.getvalue()) == (case == "end-fails"), "Self-test cleanup warning.")
            print("PASS offline", case)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="loopback fixture only, no production calls")
    args = parser.parse_args()
    try:
        self_test() if args.self_test else run()
    except (DemoError, KeyboardInterrupt) as exc:
        print("STOP:", str(exc) if isinstance(exc, DemoError) else "interrupted")
        raise SystemExit(1)
