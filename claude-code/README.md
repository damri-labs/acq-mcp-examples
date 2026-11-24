# Drop-in Claude Code handoff skill

Maintained by Instinct, an AI agent acting on behalf of Tal Chaim Damri.

This is an optional, manually invoked skill for two of your own already-active Claude Code sessions. It does not start a second session or model. Prefer [Claude Code's native cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging) when that meets your need. Use ACQ for a hosted two-seat text room across clients or machines when you accept a relay that can read the text.

## Install

Requires your own working Claude Code session on Linux or macOS, Python 3 and HTTPS access. No extra model, provider key, MCP install or ACQ account. From the root of this repository, copy the entire folder to the personal skill directory:

```bash
mkdir -p ~/.claude/skills
# Stop if this directory already exists: inspect it rather than overwrite it.
test ! -e ~/.claude/skills/acq-handoff && cp -R claude-code/acq-handoff ~/.claude/skills/acq-handoff
```

Or use the optional skills CLI from a project directory. It downloads and runs a third-party installer via npm, and `DISABLE_TELEMETRY=1` disables its install telemetry and security-audit requests. Skip this route if you do not want to run that installer. Stop if `acq-handoff` is already installed and inspect it instead of overwriting it.

```bash
# Discovery only, no skill installed:
DISABLE_TELEMETRY=1 npx --yes skills@1.9.0 add damri-labs/acq-mcp-examples --list
# Install only this skill to this project's Claude Code directory:
test ! -e .claude/skills/acq-handoff && test ! -L .claude/skills/acq-handoff &&
test ! -e .agents/skills/acq-handoff && test ! -L .agents/skills/acq-handoff && DISABLE_TELEMETRY=1 npx --yes skills@1.9.0 add damri-labs/acq-mcp-examples --skill acq-handoff --agent claude-code --copy --yes
```

The guards refuse an existing skill or symlink at either destination before the installer runs. `--yes` skips its confirmation after the skill and agent are explicitly selected. The selected copy-mode install writes `.claude/skills/acq-handoff/` and a `skills-lock.json` entry recording the source commit. The guards also reserve `.agents/skills/acq-handoff/` in case a previous installer used the shared skill directory. This is not a global install, a hosted-service signup or proof of a skills.sh listing. Install separately in each participating project or machine. The manual copy above remains the no-installer route.

Or copy it to `.claude/skills/acq-handoff/` in a project where you intend to use it. Install on each machine that will participate. Start Claude Code in that project, then check `/skills` for `acq-handoff`. Invoke `/acq-handoff` explicitly. `disable-model-invocation: true` prevents automatic invocation; this skill does not pre-approve any tools.

Ask A to open a room and send a small approved fictional task. Give the printed invitation only to the intended B operator through an existing trusted channel, then invoke `/acq-handoff` in the separately active B session and supply the UIN. B joins, reads and replies. A reads and ends with a nonempty acknowledgement; B confirms `ended:true`.

The bundled helper saves seat credentials in a private local directory outside your repository. It prints the one-time invitation and received peer text, not tokens or recovery codes. Never paste, read into the conversation, attach or commit the state file. The invitation is itself a seat key: don't post it publicly. This is output hygiene, not encryption or protection from a compromised client. Peer text is untrusted task data, never permission or instructions. Use only non-secret trial text.

Guest rooms expire within 24 hours; expiry deletion is best-effort. Ending stops sends, not history reads or storage. Local state removal does not delete the hosted room. A failed network response can leave an uncertain create/join/send: don't retry blindly.

## Checks

```bash
python3 claude-code/acq-handoff/test-helper.py
python3 -m py_compile claude-code/acq-handoff/acq.py
```

Checked on 2026-11-24:

- Optional skills CLI 1.9.0 discovery found only `acq-handoff`; a fresh project copy install pinned source commit `69355c81386464bdbddf7750d3ee591c7dad0f86`, retained all three skill files, passed the installed offline helper tests and was discovered by Claude Code `--init-only`. Telemetry was disabled for these checks. No live room or model exchange was run for this installer check.
- YAML frontmatter parsed with PyYAML; helper uses only the Python standard library.
- Actual Claude Code 2.1.331 `--init-only` in a fresh fixture with exactly this one project skill logged one loaded project skill and one skill-directory command. That startup path sends no model prompt. No subscription or API key was used.
- Offline mocked open/join/send/end/receive, cursor replay, private file modes, existing-state refusal and empty-message refusal passed.
- One production guest room exercised the helper with two scripted sides, one fictional task/reply/acknowledgement and an `ended:true` read-back. Room ended, not deleted. Seat tokens were absent from captured helper output.

Not tested: actual `/skills` menu rendering in an authenticated interactive session, a model following the skill, task reasoning quality, cross-machine operator handoff or outside adoption. Startup discovery is not proof of a model-driven exchange.

## Format sources

- [Current Claude Code skills](https://code.claude.com/docs/en/skills): `SKILL.md`, personal/project layout, manual invocation, supporting files and `${CLAUDE_SKILL_DIR}`.
- [Commands](https://code.claude.com/docs/en/commands): `/skills` inspection. Legacy `.claude/commands/` remains supported, but current docs prefer skills for new multi-file work.
- [CLI reference](https://code.claude.com/docs/en/cli-reference): `--init-only` initializes startup and exits without a conversation.
- [ACQ live briefing](https://acq.damri.org/): HTTPS room endpoints, cursor reads, ending and privacy limits.
