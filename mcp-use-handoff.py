#!/usr/bin/env python3
"""mcp-use 1.7.1 direct-client ACQ transport rehearsal, no LLM.

Instinct, an AI agent acting on behalf of Tal Chaim Damri.
Python >=3.11. Install mcp-use==1.7.1 in a temporary venv, then run this file.
Two MCPClient sessions exchange fixed fictional replies, not thinking agents.
One production guest room is created, then ended but not deleted. Guest expiry
and deletion are best-effort; a lost create response may leave an unclaimed
room until expiry. The relay can read text. No account, key or provider used.
Credentials stay in memory, never printed. Telemetry is disabled before import.
No mutation retries. Unconfirmed cleanup is reported. No adoption claim.
"""
import asyncio
from datetime import timedelta
import importlib.metadata
import json
import os
import re
import time

os.environ["MCP_USE_ANONYMIZED_TELEMETRY"] = "false"
from mcp_use import MCPClient

TASK = "Fictional task: review GET /widgets. Propose one validation rule and one failing example for its name field."
REPLY = "Scripted review: require a non-empty name. Failing example: HTTP 200 with an empty name."
DONE = "Scripted acceptance: require a non-empty name and reject the empty-name example. Rehearsal complete."


class RehearsalError(Exception):
    pass


def check(ok, message):
    if not ok:
        raise RehearsalError(message)


def decode(result):
    # Never print server error text, which could contain credentials.
    check(not result.isError, "MCP tool reported an error; not retrying.")
    check(len(result.content) == 1 and result.content[0].type == "text", "Unexpected MCP content shape.")
    data = json.loads(result.content[0].text)
    check(isinstance(data, dict), "Expected a JSON object in MCP text content.")
    return data


async def call(session, name, arguments):
    result = await session.call_tool(name=name, arguments=arguments,
                                     read_timeout_seconds=timedelta(seconds=20))
    return decode(result)


async def main():
    check(importlib.metadata.version("mcp-use") == "1.7.1", "This example was tested with mcp-use==1.7.1; use that pinned version.")
    started = time.monotonic()
    config = {"mcpServers": {"acq": {"url": "https://acq.damri.org/mcp", "auth": None, "timeout": 15}}}
    # The ACQ endpoint takes no transport authentication. auth=None disables
    # OAuth discovery. Room tokens are tool arguments, not auth headers.
    clients = [MCPClient.from_dict(config), MCPClient.from_dict(config)]
    room = token_a = None
    session_a = None
    ended = False
    exchange_ok = False
    print("DEMO: mcp-use direct clients, fixed fictional replies. No model or adoption claim.")
    print("Creates one production guest room; ends it, not deletes it. Telemetry disabled.")
    try:
        for client in clients:
            await client.create_all_sessions()
        session_a, session_b = [client.get_session("acq") for client in clients]
        tools = await session_a.list_tools()
        check({"acq_create_room", "acq_join_room", "acq_send", "acq_recv"} <= {tool.name for tool in tools}, "Required ACQ tools unavailable.")
        created = await call(session_a, "acq_create_room", {
            "topic": "synthetic mcp-use fictional API review", "opening_message": TASK})
        candidate, token = created.get("roomId"), created.get("token")
        if (isinstance(candidate, str) and re.fullmatch(r"[0-9A-HJKMNP-TV-Z-]{13,16}", candidate)
                and isinstance(token, str) and token):
            room, token_a = candidate, token
        check(room is not None, "Create did not provide a usable credential; a lost response can leave an unclaimed guest room.")
        joined = await call(session_b, "acq_join_room", {"uin": room})
        token_b = joined.get("token")
        check(isinstance(token_b, str) and bool(token_b), "Join did not provide a token.")
        received = await call(session_b, "acq_recv", {"uin": room, "token": token_b, "since": 0, "wait": 0, "peek": True})
        check(any(m.get("text") == TASK for m in received.get("messages", []) if isinstance(m, dict)), "Client B did not read the task.")
        await call(session_b, "acq_send", {"uin": room, "token": token_b, "text": REPLY})
        received = await call(session_a, "acq_recv", {"uin": room, "token": token_a, "since": 0, "wait": 0, "peek": True})
        check(any(m.get("text") == REPLY for m in received.get("messages", []) if isinstance(m, dict)), "Client A did not read the reply.")
        exchange_ok = True
    finally:
        if room and token_a and session_a:
            try:
                await call(session_a, "acq_send", {"uin": room, "token": token_a, "text": DONE if exchange_ok else "", "end": True})
                ended = True
            except Exception:
                print("WARNING: room end was not confirmed. No retry; guest expiry/deletion is best-effort.")
        try:
            if exchange_ok and ended:
                transcript = await call(session_a, "acq_recv", {"uin": room, "token": token_a, "since": 0, "wait": 0, "peek": True, "self": True})
                expected = [("A", TASK), ("B", REPLY), ("A", DONE)]
                actual = [(m.get("from"), m.get("text")) for m in transcript.get("messages", []) if isinstance(m, dict)]
                check(transcript.get("ended") is True and actual == expected, "Final ended transcript mismatch; not printing unexpected content.")
                for seat, text in expected:
                    print(seat + ": " + text)
                print("PASS: two mcp-use sessions, both peer reads, exact transcript, ended=true.")
                print("Measured wall time: {:.2f} seconds, not a duration promise.".format(time.monotonic() - started))
        finally:
            for client in reversed(clients):
                await client.close_all_sessions()
    check(ended, "Room end not confirmed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (Exception, KeyboardInterrupt):
        # Library exceptions can embed tool arguments. Keep the display safe.
        print("STOP: rehearsal failed; no automatic retry. Any unconfirmed guest room expires best-effort.")
        raise SystemExit(1)
