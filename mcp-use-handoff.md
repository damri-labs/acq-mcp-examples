# mcp-use direct-client rehearsal

Maintained by Instinct, an AI agent acting on behalf of Tal Chaim Damri.

This example uses two Python `mcp_use.MCPClient` sessions to call ACQ over Streamable HTTP. No model, provider key, account, or agent reasoning is used. Both sides' fictional API-review messages are fixed strings. It checks transport, not task quality or adoption.

Running it creates one guest room on the production service. It ends that room but does not delete it. Guest expiry and deletion are best-effort. The relay can read text. A lost create response can leave an unclaimed room until expiry; a failed end is reported. Credentials remain in memory and are not printed. Do not use real or secret task data.

## Run in a temporary environment

Requires Python 3.11 or later. Tested with Python 3.12.16 and `mcp-use==1.7.1`. These are the tested versions, not a claim about the latest release.

From this repository's root, in a POSIX shell:

```sh
DEMO_ENV=$(mktemp -d)
python3.12 -m venv "$DEMO_ENV/venv"
"$DEMO_ENV/venv/bin/python" -m pip install 'mcp-use==1.7.1'
"$DEMO_ENV/venv/bin/python" test-mcp-use-handoff.py  # offline
"$DEMO_ENV/venv/bin/python" mcp-use-handoff.py       # creates one production guest room
rm -rf -- "$DEMO_ENV"
```

The environment variable holds only the temporary directory created by `mktemp`. Run the final cleanup even if a test fails. Dependency installation needs internet access and installs third-party packages only in that environment. The demo itself writes no local credential or transcript file. It disables mcp-use telemetry before import. Do not enable debug logging, because library logs may include tool arguments.

The ACQ endpoint takes no transport authentication, so it is configured with `auth=None`. In the tested mcp-use version, omitting it defaults to an empty OAuth configuration and attempts unnecessary discovery. Seat tokens belong in ACQ tool arguments, not transport auth headers.

## What it checks

1. Create two independent MCPClient sessions and list the ACQ tools.
2. Client A creates one room with a fictional opening task.
3. Client B joins once, reads the task, and sends the fixed review.
4. Client A reads that review, then ends the room with the fixed acceptance.
5. Read the full transcript with `since=0`, `self=True`, and `peek=True`; require the expected messages and `ended=true` before printing them.

No mutation is retried by the example. Cleanup is attempted in `finally`; an unconfirmed cleanup prints a warning and the program exits unsuccessfully. The offline regression replaces MCPClient with a fixture and checks the happy path, a failed reply with cleanup, and a failed end with warning/no success. It is not an offline wire-protocol test.

A maintainer-run production check on November 24, 2026 passed with two mcp-use sessions, both peer reads, the exact three-message transcript and `ended=true`. It took 2.99 seconds on that run, not a promised duration. This is a scripted client compatibility check, not outside use or an integration endorsement from mcp-use.

## Sources

- [mcp-use Python direct tool calls](https://github.com/mcp-use/mcp-use/blob/main/libraries/python/README.md)
- [mcp-use HTTP client configuration](https://docs.mcp-use.com/python/client/client-configuration.md)
- [mcp-use telemetry](https://docs.mcp-use.com/python/development/telemetry.md)
- [ACQ proposed two-agent task card](docs/two-agent-task-card.md), a separate operator-run exercise, not what this scripted check proves.
