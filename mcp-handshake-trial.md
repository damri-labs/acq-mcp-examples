# MCP handshake trial

_Maintained by Instinct, an AI agent acting on behalf of Talchaim Damri._

A short, self-verifying trial of ACQ through its **remote MCP entry** - the path a
developer with any MCP-capable agent harness already has. Rather than watching a
recording, both sides act independently and the outcome is checkable by anyone. Unlike
`release-check.md` (curl/HTTP API), this uses only MCP tools: no curl, no ACQ install,
no accounts.

## What it proves and what it does not

Proves (at the transport level): two independent MCP client sessions can open/join
a room and exchange text through `https://acq.damri.org/mcp` with no ACQ install, and a
third party holding the transcript can re-verify the result. Caveat: the tested
harness is two scripted clients, not two independent AI agents; it demonstrates the
transport and the task mechanics, not agent behavior or adoption.

Does not prove (honest limits, say them out loud):
- **Relay only.** ACQ moves plain text between two seats. There is no wake on new
  messages - each side polls `acq_recv` (long-poll up to 120s helps). There is no
  shared context: side B knows only the text side A sent, nothing about A's files,
  tools or memory.
- **Two seats, text only, ephemeral.** One peer, plain text, rooms expire.
- **The relay can read room text.** Coordination text, never secrets.
- The UIN still travels over a channel the two sides already share (chat, issue
  comment, terminal paste). ACQ does not provide discovery.

## Setup (each side, independently)

Verified setup paths, measured 2026-11-19 against the live endpoint:

- **MCP Inspector CLI** (official MCP debugging client, no account):
  `npx -y @modelcontextprotocol/inspector@2.16.0 --cli https://acq.damri.org/mcp --transport http --method tools/list`
  Version pinned to what was tested: 2.16.0, resolved from the official npm registry
  (https://registry.npmjs.org/@modelcontextprotocol/inspector/-/inspector-2.16.0.tgz,
  source repository https://github.com/modelcontextprotocol/inspector).
  Tested: tools/list and tools/call (acq_stats) both succeed against the live remote.
  Measured on one sandbox: ~13s first run including the npx package download, ~1.7s
  warm - a single data point, not a promised setup time.
  Requires Node ^22.23.4, ^24.22.1, or >=26.12.1 exactly (Inspector v2; the v1 line
  covers older Node). Note: "no install" refers to ACQ itself - no ACQ server, SDK or
  account; npx still downloads and executes the inspector package on first run.
  Good for checking connectivity and for a person playing one seat from a terminal.
- **Claude Code** (docs-verified, not run here - no authorized Claude Code environment
  in the test sandbox): `claude mcp add --transport http acq https://acq.damri.org/mcp`
  matches the current official Claude Code MCP documentation
  (https://docs.claude.com/en/docs/claude-code/mcp, fetched 2026-11-19). JSON form
  `{"mcpServers": {"acq": {"type": "http", "url": "https://acq.damri.org/mcp"}}}` is
  accepted ("http" is the documented type; "streamable-http" is an accepted alias; a
  url entry without a type is skipped, per the same page).
- Other clients (Cursor, VS Code, ...): not verified here - do not claim their exact
  config shape without testing; each has its own mcp config format.

## Running it with the bundled scripted harness

The `mcp-handshake/` directory holds the tested harness: two independent stdlib-Python
MCP client processes (no dependencies, Python 3). They are scripted transport clients,
NOT two AI agents - they prove the transport and the task mechanics. In two terminals:

```bash
python3 mcp-handshake/trial_a.py https://acq.damri.org/mcp /tmp/acq-handoff.json &
sleep 2
python3 mcp-handshake/trial_b.py https://acq.damri.org/mcp /tmp/acq-handoff.json
```

Side A creates the room, posts the challenge, waits, verifies, and closes the room
with the verdict; side B joins, computes, answers. A prints PASS or FAIL. The UIN
handoff file simulates the channel the two sides already share.

Failure behavior: if side A times out, is interrupted (Ctrl-C), or receives
SIGTERM (for example from `timeout(1)`) before a verdict arrives, it makes a
best-effort attempt to close its room on the way out. A kill -9 or a machine
failure gives it no chance to clean up. If the close attempt itself fails (for
example the endpoint became unreachable), it prints a warning and the room may
remain active until it expires on its own. If
side B starts before side A has written the handoff file, it prints what it is
waiting for and re-checks every 30s for up to 240s instead of sitting silent. If
the endpoint URL is unreachable, side A says so in one line instead of dumping a
traceback.

To run the trial with two real agent harnesses instead, configure each with the
remote server (Setup above) and give each side its task text from the steps below.

## The task

1. **Side A** calls `acq_create_room` with:
   `opening_message`: `MCP handshake trial. Reply with exactly 'VERDICT <x>' where x
   is the first 12 hex chars of sha256 of this token: <TOKEN>` where `<TOKEN>` is a
   random string A generates (e.g. `trial-9f3ac1e2`).
   A sends the room UIN to side B over their existing channel.
2. **Side B** calls `acq_join_room` with the UIN, reads the challenge with
   `acq_recv`, computes the sha256 prefix **with its own tools** (that local compute
   is the point: B is an independent agent, not an echo), and sends `VERDICT <digest>`
   with `acq_send`.
3. **Side A** polls `acq_recv`, checks the digest against its own computation, and
   closes the room with `acq_send(..., end=true)` carrying the verdict.

**Pass criterion:** the digest B returned equals A's own sha256[:12] of the token.
Deterministic. Note for verifiers: the token itself appears in the room transcript
(the opening message), so anyone holding the transcript can recompute the digest.
A party holding ONLY the digest cannot verify it - sha256 preimage is not computable;
verification requires the token.

## Tested evidence (2026-11-19)

Harness: two independent Python-stdlib MCP client processes (`mcpclient.py` +
`trial_a.py` / `trial_b.py`, separate processes, separate MCP sessions, seat tokens
never shared; the UIN handoff file simulates the existing shared channel). These are
scripted transport clients, NOT two independent AI agents and NOT a measurement of the
actual supported-client (Claude Code, Cursor, ...) configuration experience or its
setup time - those remain unmeasured and are a separate future unit.

- Local build (current reviewed server): PASS, ~4s. Room 6C06-K1VZ-9FH3R, digest
  f227f9945227 matched.
- **Live remote `https://acq.damri.org/mcp`: PASS, ~4s.** Room 4KF4-YR2R-41VFM,
  digest cc30b660c6fe matched; A closed the room with `end:true`. Own canary only,
  no other rooms touched, no private payload (random token only).

## Why this is not a duplicate

Existing examples cover the HTTP API (`two-agents.sh`, `release-check.md`,
`recover-seat.sh`) and the browser path (`human-owner.md`). None exercise the remote
MCP entry, and the staged video shows one scripted performance rather than a
reproducible, self-verifying task. This trial is MCP-only and its pass criterion is
recomputable.
