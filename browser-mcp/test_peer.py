"""Offline only: no network and no room creation."""
import json
import unittest
from peer import CONTRACT, REPLY, decode_tool, exchange


class Fake:
    def __init__(self, fault=None):
        self.fault = fault
        self.cid = None
        self.calls = []
        self.reads = 0

    def rpc(self, *args, **kwargs):
        return {"result": {}}

    def call(self, tool, args):
        self.calls.append(tool)
        if tool == "acq_join_room":
            return {"token": "offline-token"}
        if tool == "acq_send":
            self.cid = args["cid"]
            return {"cid": "wrong" if self.fault == "send" else self.cid}
        self.reads += 1
        if self.reads == 1:
            return {"messages": [{"from": "A", "text": "wrong" if self.fault == "contract" else CONTRACT}]}
        if self.reads == 2:
            return {"messages": [{"from": "B", "text": REPLY,
                                   "cid": "wrong" if self.fault == "readback" else self.cid}]}
        return {"ended": self.fault != "end"}


class Tests(unittest.TestCase):
    def test_decode(self):
        reply = {"result": {"content": [{"type": "text", "text": '{"ok":true}'}]}}
        self.assertEqual(decode_tool(reply), {"ok": True})
        for bad in [None, {"error": {}}, {}, {"result": {"isError": True}},
                    {"result": {"content": []}},
                    {"result": {"content": [{"type": "text", "text": "bad"}]}},
                    {"result": {"content": [{"type": "text", "text": "[]"}]}}]:
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                decode_tool(bad)

    def test_success_no_secret_output(self):
        out = []
        exchange(Fake(), "offline", confirm=lambda _: "yes", emit=out.append)
        self.assertEqual(len(out), 3)
        self.assertNotIn("offline-token", " ".join(out))
        self.assertNotIn(REPLY, " ".join(out))

    def test_failures(self):
        for fault in ["contract", "send", "readback", "end"]:
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                exchange(Fake(fault), "offline", confirm=lambda _: "yes", emit=lambda _: None)
        with self.assertRaises(ValueError):
            exchange(Fake(), "offline", confirm=lambda _: "no", emit=lambda _: None)

    def test_unexpected_contract_never_sends(self):
        fake = Fake("contract")
        with self.assertRaises(ValueError):
            exchange(fake, "offline", emit=lambda _: None)
        self.assertNotIn("acq_send", fake.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
