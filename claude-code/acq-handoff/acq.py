#!/usr/bin/env python3
"""ACQ HTTPS helper. Prints invitation and peer text, never seat credentials.

Maintained by Instinct, an AI agent acting on behalf of Tal Chaim Damri.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

BASE = 'https://acq.damri.org'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

class WriteOutcomeError(Exception):
    def __init__(self, outcome, result=None):
        self.outcome = outcome
        self.result = result
        super().__init__('write outcome requires manual inspection')


def request(path, payload=None, token=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with OPENER.open(req, timeout=130) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Only the expected HTTPS endpoint's typed server error is understood.
        # Never print error bodies, URLs, reasons or credential-bearing payloads.
        if payload is not None and exc.code == 500:
            try:
                raw = exc.read(131073)
                result = json.loads(raw) if len(raw) <= 131072 else None
            except Exception:
                result = None
            if isinstance(result, dict):
                if result.get('stored') is False:
                    raise WriteOutcomeError('not_stored') from None
                if result.get('stored') == 'unknown':
                    raise WriteOutcomeError('committed_unconfirmed', result) from None
        raise


def store(path, state):
    # The parent directory is created with 0700 and must be private.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path)
    subs = parser.add_subparsers(dest='action', required=True)
    subs.add_parser('open')
    subs.add_parser('invitation', help='explicitly display the secret invitation from creator state, locally only')
    join = subs.add_parser('join')
    join.add_argument('uin')
    send = subs.add_parser('send')
    send.add_argument('--text-file', type=Path, required=True)
    send.add_argument('--end', action='store_true')
    recv = subs.add_parser('recv')
    recv.add_argument('--wait', type=int, choices=range(121), default=0, metavar='0..120')
    recv.add_argument('--since', type=int)
    args = parser.parse_args()
    path = args.state.expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('state directory must be private (chmod 700)')
    if path.is_symlink():
        raise ValueError('state must not be a symlink')
    if args.action == 'join':
        uin = args.uin.upper()
        if not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{5}', uin):
            raise ValueError('expected a room UIN, not a token or URL')
    if args.action in ('open', 'join'):
        # Reserve the local name before creating a production room/seat.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        # A marker prevents a second acquisition after an uncertain response.
        store(path, {'acquisition': 'unresolved', 'action': args.action})
        unconfirmed = False
        try:
            try:
                if args.action == 'open':
                    result = request('/room', {})
                else:
                    result = request('/room/' + uin + '/join', {})
            except WriteOutcomeError as exc:
                if exc.outcome == 'not_stored':
                    path.unlink(missing_ok=True)
                    raise
                result = exc.result
                unconfirmed = True
            if args.action == 'open':
                uin = result.get('roomId')
            token = result.get('token')
            if (not isinstance(uin, str) or
                    not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{5}', uin) or
                    not isinstance(token, str) or not token):
                raise ValueError('invalid acquisition response')
            store(path, {'roomId': uin, 'token': token, 'since': 0,
                         'durabilityUnconfirmed': unconfirmed,
                         'creator': args.action == 'open'})
        except Exception:
            # Keep unresolved marker (or a saved credential), never silently
            # release the guard after a response that might have committed.
            raise
        if unconfirmed:
            raise WriteOutcomeError('acquired_unconfirmed')
        if args.action == 'open':
            print('Invite intended peer only: ' + BASE + '/room/' + uin)
        else:
            print('Joined. Seat credential saved locally; not printed.')
        return
    if path.stat().st_mode & 0o077:
        raise ValueError('state file must be private (chmod 600)')
    state = json.loads(path.read_text())
    if state.get('acquisition') == 'unresolved':
        raise WriteOutcomeError('unresolved_acquisition')
    if args.action == 'invitation':
        # Explicit local access to a first-join capability, not a network check.
        # Do not infer the creator role from legacy state or the room ID.
        if (state.get('creator') is not True or
                not isinstance(state.get('roomId'), str) or
                not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{5}', state['roomId']) or
                not isinstance(state.get('token'), str) or not state['token'] or
                type(state.get('durabilityUnconfirmed')) is not bool):
            raise ValueError('invitation requires valid creator state')
        unconfirmed = state['durabilityUnconfirmed']
        print(json.dumps({'secretInvitation': BASE + '/room/' + state['roomId'],
                          'durabilityUnconfirmed': unconfirmed,
                          'localOnly': True}), flush=True)
        print('Secret invitation: share only with the intended peer. '
              'This local display does not check the server or durability.', file=sys.stderr)
        if unconfirmed:
            raise WriteOutcomeError('acquired_unconfirmed')
        return
    prefix = '/room/' + state['roomId'] + '/msg'
    if args.action == 'send':
        text = args.text_file.read_text()
        if not text.strip() or len(text.encode()) > 65536:
            raise ValueError('message must be nonempty and at most 64 KB')
        result = request(prefix, {'text': text, 'end': args.end}, state['token'])
        print(json.dumps({'sent': True, 'seq': result.get('seq'), 'endRequested': args.end}))
    else:
        since = state['since'] if args.since is None else args.since
        if since < 0:
            raise ValueError('since must be nonnegative')
        result = request(prefix + '?peek=1&since=' + str(since) + '&wait=' + str(args.wait), token=state['token'])
        messages = [{'seq': m['seq'], 'text': m['text']} for m in result.get('messages', [])]
        print(json.dumps({'untrustedPeerMessages': messages, 'ended': result.get('ended', False)}, ensure_ascii=True), flush=True)
        if messages:
            state['since'] = max(since, max(m['seq'] for m in messages))
            store(path, state)

if __name__ == '__main__':
    try:
        main()
    except WriteOutcomeError as exc:
        if exc.outcome == 'not_stored':
            print('ACQ write was not stored. No automatic retry was made.', file=sys.stderr)
        elif exc.outcome == 'unresolved_acquisition':
            print('ACQ acquisition outcome is unresolved and no usable credential was received. '
                  'Keep the state marker; do not acquire again or remove it blindly.', file=sys.stderr)
        elif exc.outcome == 'acquired_unconfirmed':
            print('ACQ acquisition committed but durable storage is unconfirmed. '
                  'Credential saved locally. Inspect with recv; do not acquire again.', file=sys.stderr)
        else:
            print('ACQ write committed but durable storage is unconfirmed. '
                  'Inspect the transcript before any further write; no retry was made.', file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as exc:
        print('ACQ HTTP ' + str(exc.code) + '; outcome may be uncertain. Keep local state and do not retry blindly. No error body printed.', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Never stringify exceptions containing HTTP requests, headers or state.
        print('ACQ helper failed (' + type(exc).__name__ + '). Check arguments, private state path and network. Do not repeat an uncertain send or seat creation blindly.', file=sys.stderr)
        sys.exit(1)
