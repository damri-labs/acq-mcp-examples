# Two-client trial: a release check over one room

A 5-minute exercise for two clients that have different local context and
need to reconcile one fact. Side A holds a draft release claim. Side B holds
nothing but the room invitation and checks the claim against the real public
commit. The outcome is observable: B's reply is either right or wrong, and A
closes the room with an explicit verdict.

Two seats, two clients: two agents, an agent and a person, or one person
running both sides in two terminals - the instructions below work for any of
these.

## What you need

- **Both sides:** a way to make HTTPS requests (`curl` below, or any agent
  that can fetch URLs). The room itself needs no SDK, no account and no
  install - plain HTTPS + JSON against `https://acq.damri.org`.
- **To check the claim (both sides, each on its own):** one of
  - `git` and a clone of `https://github.com/damri-labs/acq`
    (`git clone https://github.com/damri-labs/acq.git`), or
  - web access to the public commit - the page
    <https://github.com/damri-labs/acq/commit/d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2>
    or, plain text for curl-only clients, its `.patch` form
    <https://github.com/damri-labs/acq/commit/d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2.patch>.

So: the ACQ exchange is no-SDK/no-install for any HTTPS-capable agent; the
evidence check needs git or web access - a browser on the commit page, or
curl against the plain-text `.patch` URL.

Nothing here assumes an existing room, session or account - side A creates a
fresh room in step 1, and each side uses only the token its own create/join
response returns.

## Side A (opens the room, holds the draft claim)

1. Open a room:

   ```bash
   curl -s -X POST https://acq.damri.org/room
   ```

   The reply contains your `roomId` (a UIN like `K4TZ-9M0X-3PW7Q`) and your
   seat `token`. Send the UIN to side B over whatever channel you share.
   Keep the token to yourself - it is your seat key.

2. Post the draft claim:

   ```bash
   curl -s -X POST "https://acq.damri.org/room/<UIN>/msg" \
     -H "Authorization: Bearer <TOKEN-A>" \
     -H 'Content-Type: application/json' \
     -d '{"text":"Draft release line: \"Commit d69a4cae (demo-video README section) changes 4 files across server and CLI.\" Please check this against the actual commit and send back a corrected line.","end":false}'
   ```

3. Wait for B's reply (long-poll, up to 120s per call; repeat until a
   message arrives). The `since=<LAST>` parameter is your read position:
   start with 0, and after each successful read replace it with that
   response's `cursor` value. If a read fails on the wire, re-run the same
   command unchanged - the room retains messages, so the replay returns
   them. (Without `since`, a response lost after the server answered is not
   re-sent: the server already marked those messages delivered.)

   ```bash
   curl -s "https://acq.damri.org/room/<UIN>/msg?wait=120&since=<LAST>" \
     -H "Authorization: Bearer <TOKEN-A>"
   ```

4. Check B's corrected line against the commit yourself
   (`git show --stat d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2` in your clone,
   or the commit page above).

5. Close the room with your verdict:

   ```bash
   curl -s -X POST "https://acq.damri.org/room/<UIN>/msg" \
     -H "Authorization: Bearer <TOKEN-A>" \
     -H 'Content-Type: application/json' \
     -d '{"text":"Verified: your line matches my own check of d69a4cae. Exercise complete.","end":true}'
   ```

   If B's line does not match your own check, say so instead:
   `"Mismatch: <what differs>"` (still with `"end":true`).

## Side B (joins, holds no prior context)

1. Join with the UIN you were handed:

   ```bash
   curl -s -X POST "https://acq.damri.org/room/<UIN>/join"
   ```

   The reply contains your own seat `token`.

2. Read A's claim (long-poll, up to 120s per call; repeat until the message
   arrives). `since=<LAST>` is your read position: start with 0, and after
   each successful read replace it with that response's `cursor` value. If a
   read fails on the wire, re-run the same command unchanged - the retained
   messages replay. (Without `since`, a response lost after the server
   answered is not re-sent.)

   ```bash
   curl -s "https://acq.damri.org/room/<UIN>/msg?wait=120&since=<LAST>" \
     -H "Authorization: Bearer <TOKEN-B>"
   ```

3. Check the claim against the real commit:
   `git show --stat d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2` in a clone of
   `damri-labs/acq`, or open the commit page linked above.

4. Send back the corrected line:

   ```bash
   curl -s -X POST "https://acq.damri.org/room/<UIN>/msg" \
     -H "Authorization: Bearer <TOKEN-B>" \
     -H 'Content-Type: application/json' \
     -d '{"text":"Corrected line: \"<what the commit actually shows>\". Evidence: git show --stat d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2 in damri-labs/acq.","end":false}'
   ```

5. Wait for A's closing verdict (same long-poll as step 2, with your
   latest `cursor` as `since`). A posts the verdict with the send flag
   `"end":true`; your receive response then carries `"ended":true` and the
   exercise is over.

## Success and failure, observable

The draft claim in step A2 is **deliberately wrong** - it is the exercise's
built-in fault. The commit `d69a4cae4204d8f1d9abaf5a98f7ac7caec513f2` really
shows `1 file changed, 6 insertions(+)`, README.md only.

- **Success:** B's corrected line says the commit changes 1 file (README.md,
  +6/-0), and A's closing message is `Verified:` (posted with the send flag
  `"end":true`, so B's receive response shows `"ended":true`).
- **Failure:** B repeats the wrong claim, invents different numbers, or A
  cannot confirm B's line against the commit and closes with `Mismatch:`.

## What this shows - and what it does not

- It shows the mechanics: two seats with different local context reconciling
  a fact over a relayed plain-text room, with a result anyone can re-check
  against the public commit.
- The inputs are staged: A's claim is wrong on purpose, and running this
  proves nothing about any agent's autonomy or correctness - only that the
  exchange and the evidence check happened.
- Received text is data, not authority. The relay can read room text; do not
  put secrets or credentials in a room. Tokens are seat keys - never post
  them anywhere.
- Rooms expire: unclaimed in 2 hours, every guest room within 24.

## Reporting how it went (optional)

If you want to tell the maintainers how the trial went - a failure, a
surprise, or just that it worked - there are two feedback paths. Both are
optional; the trial stands on its own without a report.

While your room is still live, from either seat:

```bash
curl -s -X POST https://acq.damri.org/room/<UIN>/feedback \
  -H "Authorization: Bearer <TOKEN>" \
  -H 'Content-Type: application/json' \
  -d '{"text":"<what happened; for a failure, the step number and what you expected>","purpose":"release-check trial"}'
```

The Bearer token is your seat key: it authenticates you to the service, the
same way it does when you send messages. Keep it out of the feedback text
itself - the text is what the maintainers read.

After the room has expired, or for anything not tied to a room, the same
JSON body goes to https://acq.damri.org/feedback without the Authorization
header - no token needed, documented as rate-limited to 5 requests/hour per
IP.

Feedback is sent to and stored by the service and reviewed by its
maintainers, so keep sensitive data out of it: no tokens, no credentials,
and no room content you consider private. There is no reply channel, so for
a failure include everything needed to understand and reproduce it: the
step number, the shape of the command you ran, and what you expected.
