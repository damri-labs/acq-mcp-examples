"""Offline flow regression, no service calls and no model.
Instinct, an AI agent acting on behalf of Tal Chaim Damri.
Run in the pinned example venv: python test-mcp-use-handoff.py
"""
import asyncio
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("demo", Path(__file__).with_name("mcp-use-handoff.py"))
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


async def test(case):
    state = {"calls": [], "messages": [], "closed": 0, "ended": False}

    class Session:
        async def list_tools(self):
            return [SimpleNamespace(name=n) for n in ["acq_create_room", "acq_join_room", "acq_send", "acq_recv"]]

        async def call_tool(self, name, arguments, **_):
            state["calls"].append(name)
            if name == "acq_create_room":
                state["messages"].append({"from": "A", "text": arguments["opening_message"]})
                data = {"roomId": "K4TZ-9M0X-3PW7Q", "token": "fixture-private-a"}
            elif name == "acq_join_room":
                data = {"token": "fixture-private-b"}
            elif name == "acq_recv":
                data = {"messages": state["messages"], "ended": state["ended"]}
            else:
                if (case == "reply-fails" and not arguments.get("end")) or (case == "end-fails" and arguments.get("end")):
                    raise RuntimeError("fixture")
                state["messages"].append({"from": "A" if arguments.get("end") else "B", "text": arguments["text"]})
                state["ended"] = bool(arguments.get("end"))
                data = {"seq": len(state["messages"])}
            return SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text=json.dumps(data))])

    class Client:
        @classmethod
        def from_dict(cls, config):
            assert config["mcpServers"]["acq"]["auth"] is None
            return cls()

        async def create_all_sessions(self):
            pass

        def get_session(self, _):
            return Session()

        async def close_all_sessions(self):
            state["closed"] += 1

    demo.MCPClient = Client
    output = io.StringIO()
    failed = False
    try:
        with contextlib.redirect_stdout(output):
            await demo.main()
    except (demo.RehearsalError, RuntimeError):
        failed = True
    assert failed == (case != "happy"), case
    assert state["closed"] == 2, case
    assert len(state["calls"]) == {"happy": 7, "reply-fails": 5, "end-fails": 6}[case], state
    assert "fixture-private" not in output.getvalue()
    assert ("PASS:" in output.getvalue()) == (case == "happy")
    assert ("WARNING:" in output.getvalue()) == (case == "end-fails")
    print("PASS offline", case)


for case in ["happy", "reply-fails", "end-fails"]:
    asyncio.run(test(case))
